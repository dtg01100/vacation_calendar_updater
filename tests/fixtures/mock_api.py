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


class MockableGoogleApi:
    """A mock API that supports MagicMock-style assertions and internal state.

    This class combines real method implementations with MagicMock-style
    call tracking. Use `mockable_api._mock_delete_event.called` and
    `mockable_api._mock_delete_event.assert_called_with()` for assertions,
    while the real methods do the actual work for stateful tests.
    """

    def __init__(self) -> None:
        """Initialize the mock API with empty state."""
        self._events: dict[str, dict[str, Any]] = {}
        self._email_sent: list[dict[str, Any]] = []
        self._calendars: dict[str, dict[str, Any]] = {}
        # MagicMock instances for assertion support
        self._mock_list_calendars = MagicMock()
        self._mock_user_email = MagicMock()
        self._mock_delete_event = MagicMock()
        self._mock_send_email = MagicMock()
        self._mock_create_event = MagicMock()
        self._mock_update_event = MagicMock()
        # Pre-configure common return values
        self._mock_list_calendars.return_value = [
            {"id": "cal_primary", "summary": "Primary"},
            {"id": "cal_work", "summary": "Work Calendar"},
        ]
        self._mock_user_email.return_value = "[REDACTED]"
        self._mock_create_event.return_value = CreatedEvent(
            event_id="new_0", calendar_id="cal_primary"
        )
        self._mock_update_event.return_value = CreatedEvent(
            event_id="updated", calendar_id="cal_primary"
        )

    def list_calendars(self) -> list[dict[str, Any]]:
        """List calendars."""
        return self._mock_list_calendars()

    def user_email(self) -> str:
        """Get user email."""
        return self._mock_user_email()

    def list_events(
        self,
        calendar_id: str,
        time_min: dt.datetime | None = None,
        time_max: dt.datetime | None = None,
    ) -> list[dict[str, Any]]:
        """List events from internal store."""
        events = list(self._events.values())
        return [e for e in events if e.get("calendar_id") == calendar_id]

    def create_event(
        self,
        calendar_id: str,
        summary: str,
        start: dt.datetime,
        end: dt.datetime,
    ) -> CreatedEvent:
        """Create an event and return CreatedEvent."""
        self._mock_create_event(calendar_id, summary, start, end)
        event_id = f"new_{len(self._events)}"
        self._events[event_id] = {
            "id": event_id,
            "calendar_id": calendar_id,
            "summary": summary,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        return CreatedEvent(event_id=event_id, calendar_id=calendar_id)

    def delete_event(self, event: Any) -> None:
        """Delete an event and track the call.

        Accepts either an event_id string or an object with event_id attribute.
        The call is tracked via MagicMock for assertion support.
        """
        # Extract event_id from object or use directly
        event_id = getattr(event, "event_id", event)
        # Track the call (use str to ensure hashability)
        self._mock_delete_event(str(event_id))
        # Only try to delete from internal store if it's a valid key
        if isinstance(event_id, str) and event_id in self._events:
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
        self._mock_update_event(event_id, calendar_id, summary, start, end)
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
        recipient: str,
        subject: str,
        body: str,
        *,
        enabled: bool = True,
    ) -> None:
        """Record email sending and track the call.

        Args:
            recipient: Email address to send to
            subject: Email subject line
            body: Email body text
            enabled: Whether email sending is enabled - if False, no email is recorded
        """
        if not enabled:
            return  # Respect the enabled flag like the real implementation
        self._mock_send_email(recipient, subject, body)
        self._email_sent.append(
            {
                "to": recipient,
                "subject": subject,
                "body": body,
                "event_ids": [],
            }
        )

    def get_sent_emails(self) -> list[dict[str, Any]]:
        """Get all sent emails."""
        return self._email_sent.copy()

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

    def reset(self) -> None:
        """Reset all mock data."""
        self._events.clear()
        self._email_sent.clear()
        self._calendars.clear()
        self._mock_delete_event.reset_mock()
        self._mock_send_email.reset_mock()
        self._mock_create_event.reset_mock()
        self._mock_update_event.reset_mock()


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
    `mock_api._mock_method.return_value` or `mock_api._mock_method.side_effect`
    for assertion tracking. The real methods do actual work.
    """
    return MockableGoogleApi()