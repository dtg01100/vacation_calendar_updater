import base64
import datetime as dt
from types import SimpleNamespace

import pytest

from app import config as app_config
from app import services
from app.services import DEFAULT_CREDENTIAL_NAME, GoogleApi


class FakePage:
    def __init__(self, response):
        self.response = response

    def execute(self):
        return self.response


class FakeCreds:
    def __init__(self, invalid: bool = False):
        self.invalid = invalid
        self.authorized_with = None

    def authorize(self, http):
        self.authorized_with = http
        return f"authed:{http}"


class FakeSend:
    def __init__(self, sink):
        self.sink = sink

    def execute(self):
        return self.sink


class FakeMessages:
    def __init__(self):
        self.calls = []

    def send(self, userId, body):
        self.calls.append((userId, body))
        return FakeSend(self.calls)


class FakeUsersMessages:
    def __init__(self):
        self.messages_service = FakeMessages()

    def messages(self):
        return self.messages_service

    def getProfile(self, userId):
        return FakePage({"emailAddress": "user@example.com"})


class FakeGmailService:
    def __init__(self):
        self.user_calls = 0
        self.users_service = FakeUsersMessages()

    def users(self):
        self.user_calls += 1
        return self.users_service


class FakeCalendarList:
    def __init__(self, pages):
        self.pages = pages
        self.requests = []

    def calendarList(self):
        return self

    def list(self, pageToken=None):
        self.requests.append(pageToken)
        return FakePage(self.pages[pageToken])


class FakeEvents:
    def __init__(self):
        self.calls = []

    def insert(self, calendarId, body):
        self.calls.append((calendarId, body))
        return FakePage({"id": "evt-123"})


class FakeCalendarService:
    def __init__(self, events_service=None, calendar_pages=None):
        self.events_service = events_service or FakeEvents()
        self.calendar_pages = calendar_pages
        self._calendar_list = (
            FakeCalendarList(calendar_pages) if calendar_pages is not None else None
        )

    def events(self):
        return self.events_service

    def calendarList(self):
        if self._calendar_list is None:
            raise AssertionError("calendar_pages not provided")
        return self._calendar_list


def test_ensure_connected_requires_dependencies(monkeypatch):
    monkeypatch.setattr(services, "httplib2", None)
    monkeypatch.setattr(services, "discovery", None)
    monkeypatch.setattr(services, "client", None)
    monkeypatch.setattr(services, "tools", None)
    monkeypatch.setattr(services, "Storage", None)

    api = GoogleApi(client_secret="dummy.json")
    with pytest.raises(ImportError):
        api.ensure_connected()


def test_ensure_connected_builds_services_once(monkeypatch):
    fake_creds = FakeCreds()

    monkeypatch.setattr(services, "httplib2", SimpleNamespace(Http=lambda: "http"))
    build_calls = []

    def fake_build(name, version, http=None, static_discovery=False):
        build_calls.append((name, version, http, static_discovery))
        return f"{name}-{version}-service"

    monkeypatch.setattr(services, "discovery", SimpleNamespace(build=fake_build))
    monkeypatch.setattr(GoogleApi, "_get_credentials", lambda self: fake_creds)

    api = GoogleApi(client_secret="dummy.json")
    api.ensure_connected()
    api.ensure_connected()

    assert build_calls == [
        ("calendar", "v3", "authed:http", False),
        ("gmail", "v1", "authed:http", False),
    ]
    assert api.calendar_service() == "calendar-v3-service"
    assert api.gmail_service() == "gmail-v1-service"


def test_list_calendars_handles_pagination(monkeypatch):
    pages = {
        None: {
            "items": [
                {"summary": "Team", "accessRole": "owner"},
                {"summary": "Ignore", "accessRole": "reader"},
            ],
            "nextPageToken": "page2",
        },
        "page2": {
            "items": [
                {"summary": "Personal", "accessRole": "writer"},
            ]
        },
    }

    api = GoogleApi(client_secret="dummy.json")
    api._calendar_service = FakeCalendarService(calendar_pages=pages)
    api._gmail_service = object()  # mark connected

    summaries, calendars = api.list_calendars()

    assert summaries == ["Team", "Personal"]
    assert [item["summary"] for item in calendars] == ["Team", "Ignore", "Personal"]
    assert api._calendar_service.calendarList().requests == [None, "page2"]


def test_create_event_builds_body(monkeypatch):
    monkeypatch.setattr(services, "rfc3339", SimpleNamespace(rfc3339=lambda x: f"RFC:{x.isoformat()}"))

    events = FakeEvents()
    api = GoogleApi(client_secret="dummy.json")
    api._calendar_service = FakeCalendarService(events_service=events)
    api._gmail_service = object()

    start = dt.datetime(2025, 5, 17, 9, 30)
    end = dt.datetime(2025, 5, 17, 10, 45)

    created = api.create_event("cal-123", "Planning", start, end)

    assert created.event_id == "evt-123"
    calendar_id, body = events.calls[0]
    assert calendar_id == "cal-123"
    assert body["summary"] == "Planning"
    assert body["start"]["dateTime"] == f"RFC:{start.isoformat()}"
    assert body["end"]["dateTime"] == f"RFC:{end.isoformat()}"


def test_send_email_respects_enabled_flag(monkeypatch):
    api = GoogleApi(client_secret="dummy.json")
    api._gmail_service = None

    api.send_email("to@example.com", "Hi", "Body", enabled=False)

    assert api._gmail_service is None


def test_send_email_encodes_and_sends(monkeypatch):
    gmail = FakeGmailService()
    api = GoogleApi(client_secret="dummy.json")
    api._gmail_service = gmail
    monkeypatch.setattr(api, "ensure_connected", lambda: None)

    api.send_email("to@example.com", "Subject", "Hello world", enabled=True)

    assert len(gmail.users_service.messages_service.calls) == 1
    user, payload = gmail.users_service.messages_service.calls[0]
    assert user == "me"
    raw = base64.urlsafe_b64decode(payload["raw"]).decode()
    assert "subject: subject" in raw.lower()
    assert "to@example.com" in raw


def test_user_email_uses_profile(monkeypatch):
    gmail = FakeGmailService()
    api = GoogleApi(client_secret="dummy.json")
    api._gmail_service = gmail
    monkeypatch.setattr(api, "ensure_connected", lambda: None)

    assert api.user_email() == "user@example.com"
    assert gmail.user_calls == 1


def test_get_credentials_uses_config_directory_and_caches(monkeypatch, tmp_path):
    cred_dir = tmp_path / "config"
    credentials_dir = cred_dir / "credentials"
    credentials_dir.mkdir(parents=True)
    credential_path = credentials_dir / DEFAULT_CREDENTIAL_NAME
    credential_path.write_text("stub")

    created_paths = []
    fake_creds = FakeCreds(invalid=False)

    class FakeStorage:
        def __init__(self, path):
            created_paths.append(path)
            self.path = path

        def get(self):
            return fake_creds

    monkeypatch.setattr(app_config, "get_config_directory", lambda: cred_dir)
    monkeypatch.setattr(services, "Storage", FakeStorage)

    api = GoogleApi(client_secret="dummy.json")
    first = api._get_credentials()
    second = api._get_credentials()

    assert first is fake_creds
    assert second is fake_creds
    assert created_paths == [credential_path]
