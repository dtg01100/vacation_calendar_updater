"""Mock Google API fixture for testing without network access."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from app.services import CreatedEvent, EnhancedCreatedEvent


class MockGoogleApi:
    """Mock GoogleApi that simulates API behavior without network calls.

    Supports:
    - Calendar listing
    - Event creation
    - Event deletion
    - Event updates
    - Email sending
    - Error simulation (404, 410, etc.)
    """

    def __init__(self) -> None:
        """Initialize mock API with empty data stores."""
        self._calendars: dict[str, dict[str, Any]] = {}
        self._events: dict[str, dict[str, Any]] = {}
        self._email_sent: list[dict[str, Any]] = []
        self._error_on_delete: set[str] = set()
        self._error_on_create: bool = False
        self._error_response: MagicMock | None = None

    def add_calendar(self, calendar_id: str, summary: str = "Test Calendar") -> None:
        """Add a calendar to the mock."""
        self._calendars[calendar_id] = {
            "id": calendar_id,
            "summary": summary,
        }

    def add_event(
        self,
        event_id: str,
        calendar_id: str,
        summary: str = "Test Event",
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
    ) -> None:
        """Add an event to the mock."""
        if start is None:
            start = dt.datetime.now()
        if end is None:
            end = start + dt.timedelta(hours=1)

        self._events[event_id] = {
            "id": event_id,
            "calendar_id": calendar_id,
            "summary": summary,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }

    def configure_delete_error(self, event_id: str, status: int = 404) -> None:
        """Configure a specific event to raise error on delete."""
        self._error_on_delete.add(event_id)
        self._error_response = MagicMock()
        self._error_response.status = status

    def configure_create_error(self) -> None:
        """Configure create operations to fail."""
        self._error_on_create = True
        self._error_response = MagicMock()
        self._error_response.status = 500

    def list_calendars(self) -> list[dict[str, Any]]:
        """Return list of calendars."""
        return list(self._calendars.values())

    def get_calendars(self) -> list[dict[str, Any]]:
        """Return list of calendars (alias for list_calendars)."""
        return self.list_calendars()

    def create_event(
        self,
        calendar_id: str,
        summary: str,
        start: dt.datetime,
        end: dt.datetime,
        notification_email: str | None = None,
    ) -> CreatedEvent:
        """Create an event and return CreatedEvent."""
        if self._error_on_create and self._error_response:
            raise HttpError(self._error_response, b"Internal Error")

        event_id = f"evt_{len(self._events)}"
        self._events[event_id] = {
            "id": event_id,
            "calendar_id": calendar_id,
            "summary": summary,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        return CreatedEvent(event_id=event_id, calendar_id=calendar_id)

    def delete_event(self, event_id: str) -> None:
        """Delete an event."""
        if event_id in self._error_on_delete:
            if self._error_response:
                raise HttpError(self._error_response, b"Not found")
            raise HttpError(MagicMock(status=404), b"Not found")

        if event_id in self._events:
            del self._events[event_id]

    def update_event(
        self,
        event_id: str,
        calendar_id: str,
        summary: str,
        start: dt.datetime,
        end: dt.datetime,
    ) -> CreatedEvent:
        """Update an event and return CreatedEvent."""
        if event_id in self._events:
            self._events[event_id].update(
                {
                    "summary": summary,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                }
            )
        else:
            self._events[event_id] = {
                "id": event_id,
                "calendar_id": calendar_id,
                "summary": summary,
                "start": start.isoformat(),
                "end": end.isoformat(),
            }
        return CreatedEvent(event_id=event_id, calendar_id=calendar_id)

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        event_ids: list[str] | None = None,
    ) -> None:
        """Record email sending."""
        self._email_sent.append(
            {
                "to": to,
                "subject": subject,
                "body": body,
                "event_ids": event_ids or [],
            }
        )

    def get_sent_emails(self) -> list[dict[str, Any]]:
        """Get all sent emails."""
        return self._email_sent.copy()

    def reset(self) -> None:
        """Reset all mock data."""
        self._calendars.clear()
        self._events.clear()
        self._email_sent.clear()
        self._error_on_delete.clear()
        self._error_on_create = False
        self._error_response = None


class MockableGoogleApi(MagicMock):
    """A MagicMock-based API that supports both mock patterns and internal state.

    This class extends MagicMock to support `return_value` and `side_effect`
    patterns used in integration tests, while also maintaining internal state
    for methods that need it.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._events: dict[str, dict[str, Any]] = {}
        self._email_sent: list[dict[str, Any]] = []
        self._call_count: dict[str, int] = {"create_event": 0, "delete_event": 0}

    def add_event(
        self,
        event_id: str,
        calendar_id: str,
        summary: str = "Test Event",
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
    ) -> None:
        """Add an event to the internal store."""
        if start is None:
            start = dt.datetime.now()
        if end is None:
            end = start + dt.timedelta(hours=1)

        self._events[event_id] = {
            "id": event_id,
            "calendar_id": calendar_id,
            "summary": summary,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }

    def delete_event(self, event_id: str) -> None:
        """Delete an event from internal store."""
        if event_id in self._events:
            del self._events[event_id]

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        event_ids: list[str] | None = None,
    ) -> None:
        """Record email sending."""
        self._email_sent.append(
            {
                "to": to,
                "subject": subject,
                "body": body,
                "event_ids": event_ids or [],
            }
        )

    def get_sent_emails(self) -> list[dict[str, Any]]:
        """Get all sent emails."""
        return self._email_sent.copy()

    @property
    def call_count(self) -> dict[str, int]:
        """Get call counts for methods."""
        return self._call_count


@pytest.fixture
def mock_api() -> MockGoogleApi:
    """Create a MockGoogleApi instance with test data.

    Returns a configured MockGoogleApi with:
    - Primary calendar (cal_primary)
    - Work calendar (cal_work)
    - Two existing events
    """
    api = MockGoogleApi()
    api.add_calendar("cal_primary", "Primary")
    api.add_calendar("cal_work", "Work Calendar")
    api.add_event(
        "evt_existing_1",
        "cal_primary",
        "Existing Event 1",
        dt.datetime(2024, 3, 15, 9, 0),
        dt.datetime(2024, 3, 15, 17, 0),
    )
    api.add_event(
        "evt_existing_2",
        "cal_primary",
        "Existing Event 2",
        dt.datetime(2024, 3, 16, 9, 0),
        dt.datetime(2024, 3, 16, 17, 0),
    )
    return api


@pytest.fixture
def empty_api() -> MockGoogleApi:
    """Create an empty MockGoogleApi with no data."""
    return MockGoogleApi()


@pytest.fixture
def mockable_api() -> MockableGoogleApi:
    """Create a MockableGoogleApi that supports MagicMock patterns.

    Use this fixture for integration tests that need to use
    `mock_api.method.return_value` or `mock_api.method.side_effect`.
    """
    api = MockableGoogleApi()
    # Default return values
    api.list_calendars.return_value = [
        {"id": "cal_primary", "summary": "Primary"},
        {"id": "cal_work", "summary": "Work Calendar"},
    ]
    api.user_email.return_value = "[REDACTED]"
    return api