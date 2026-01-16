from __future__ import annotations

import argparse
import base64
import datetime as dt
import os
import sys
from dataclasses import dataclass
from email.mime.text import MIMEText
from pathlib import Path

import pyparsing as pp

# Compatibility for pyparsing>=3 where DelimitedList was renamed to delimitedList
if not hasattr(pp, "DelimitedList") and hasattr(pp, "delimitedList"):
    pp.DelimitedList = pp.delimitedList

try:
    import httplib2
    import rfc3339
    from googleapiclient import discovery
    from oauth2client import client, tools
    from oauth2client.file import Storage
except ImportError:  # pragma: no cover - graceful fallback for test environments
    httplib2 = None
    rfc3339 = None
    discovery = None
    client = None
    tools = None
    Storage = None

SCOPES = "https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly"
APPLICATION_NAME = "Vacation Calendar Tool"
DEFAULT_CREDENTIAL_NAME = "vacation-calendar-tool.json"


@dataclass
class CreatedEvent:
    event_id: str
    calendar_id: str


@dataclass
class EnhancedCreatedEvent:
    event_id: str = ""
    calendar_id: str = ""
    event_name: str = ""
    start_time: dt.datetime | None = None
    end_time: dt.datetime | None = None
    created_at: dt.datetime | None = None
    batch_id: str | None = None
    request_snapshot: dict | None = None
    calendar_name: str | None = None


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - _MEIPASS only exists when frozen
        base_path = os.path.abspath(".")

    return str(Path(base_path) / relative_path)


def compat_urlsafe_b64encode(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii")


class GoogleApi:
    def __init__(
        self,
        client_secret: str | None = None,
        credential_name: str = DEFAULT_CREDENTIAL_NAME,
    ) -> None:
        self.client_secret = (
            client_secret
            or os.environ.get("CLIENT_SECRET_PATH")
            or resource_path("client_secret.json")
        )
        self.credential_name = credential_name
        self._calendar_service = None
        self._gmail_service = None
        self._credentials = None

    def ensure_connected(self) -> None:
        if self._calendar_service and self._gmail_service:
            return
        if any(dep is None for dep in (httplib2, discovery, client, tools, Storage)):
            raise ImportError(
                "Google API dependencies are not installed. Please install requirements.txt to use GoogleApi."
            )
        credentials = self._get_credentials()
        http = credentials.authorize(httplib2.Http())
        self._calendar_service = discovery.build(
            "calendar", "v3", http=http, static_discovery=False
        )
        self._gmail_service = discovery.build(
            "gmail", "v1", http=http, static_discovery=False
        )

    def calendar_service(self):
        self.ensure_connected()
        return self._calendar_service

    def gmail_service(self):
        self.ensure_connected()
        return self._gmail_service

    def user_email(self) -> str:
        self.ensure_connected()
        profile = self._gmail_service.users().getProfile(userId="me").execute()
        return profile.get("emailAddress", "")

    def list_calendars(self) -> tuple[list[str], list[dict]]:
        self.ensure_connected()
        page_token = None
        calendar_summary_list: list[str] = []
        calendars: list[dict] = []
        while True:
            calendar_list_from_net = (
                self._calendar_service.calendarList()
                .list(pageToken=page_token)
                .execute()
            )
            calendars.extend(calendar_list_from_net.get("items", []))
            for entry in calendar_list_from_net.get("items", []):
                if entry.get("accessRole") != "reader" and "summary" in entry:
                    calendar_summary_list.append(entry["summary"])
            page_token = calendar_list_from_net.get("nextPageToken")
            if not page_token:
                break
        return calendar_summary_list, calendars

    def create_event(self, calendar_id: str, summary: str, start, end) -> CreatedEvent:
        self.ensure_connected()
        body = {
            "summary": summary,
            "start": {"dateTime": rfc3339.rfc3339(start)},
            "end": {"dateTime": rfc3339.rfc3339(end)},
            "reminders": {"useDefault": False},
        }
        event = (
            self._calendar_service.events()
            .insert(calendarId=calendar_id, body=body)
            .execute()
        )
        return CreatedEvent(event_id=event.get("id"), calendar_id=calendar_id)

    def delete_event(self, created_event: CreatedEvent) -> None:
        self.ensure_connected()
        self._calendar_service.events().delete(
            calendarId=created_event.calendar_id, eventId=created_event.event_id
        ).execute()

    def send_email(
        self, recipient: str, subject: str, body: str, *, enabled: bool
    ) -> None:
        if not enabled:
            return
        self.ensure_connected()
        message = MIMEText(body)
        message["to"] = recipient
        message["from"] = "me"
        message["subject"] = subject
        payload = {"raw": compat_urlsafe_b64encode(message.as_string())}
        self._gmail_service.users().messages().send(userId="me", body=payload).execute()

    def _get_credentials(self):
        if self._credentials:
            return self._credentials

        # Use config directory utility for cross-platform support
        from .config import get_config_directory

        credential_dir = get_config_directory() / "credentials"
        credential_dir.mkdir(parents=True, exist_ok=True)
        credential_path = credential_dir / self.credential_name

        # Create store at credential path
        store = Storage(credential_path)
        credentials = None
        if credential_path.exists():
            credentials = store.get()

        if not credentials or credentials.invalid:
            flow = client.flow_from_clientsecrets(self.client_secret, SCOPES)
            flow.user_agent = APPLICATION_NAME
            try:
                flag_parser = argparse.ArgumentParser(parents=[tools.argparser])
                flags = flag_parser.parse_args([])
            except Exception:
                flags = None
            if flags:
                credentials = tools.run_flow(flow, store, flags)
            else:  # pragma: no cover - legacy fallback
                credentials = tools.run(flow, store)
        self._credentials = credentials
        return credentials
