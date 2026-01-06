"""Tests for calendar API services."""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock

import pytest

from app.services import CreatedEvent, EnhancedCreatedEvent, GoogleApi


class TestGoogleApi:
    """Tests for GoogleApi class."""

    @pytest.fixture
    def mock_api(self):
        """Create a mock GoogleApi."""
        api = MagicMock(spec=GoogleApi)
        return api

    def test_google_api_has_calendar_service(self, mock_api):
        """Test that GoogleApi has calendar_service method."""
        assert hasattr(GoogleApi, "calendar_service")

    def test_google_api_has_gmail_service(self, mock_api):
        """Test that GoogleApi has gmail_service method."""
        assert hasattr(GoogleApi, "gmail_service")

    def test_google_api_has_list_calendars(self, mock_api):
        """Test that GoogleApi has list_calendars method."""
        assert hasattr(GoogleApi, "list_calendars")

    def test_google_api_has_create_event(self, mock_api):
        """Test that GoogleApi has create_event method."""
        assert hasattr(GoogleApi, "create_event")

    def test_google_api_has_delete_event(self, mock_api):
        """Test that GoogleApi has delete_event method."""
        assert hasattr(GoogleApi, "delete_event")

    def test_google_api_has_send_email(self, mock_api):
        """Test that GoogleApi has send_email method."""
        assert hasattr(GoogleApi, "send_email")


class TestEnhancedCreatedEvent:
    """Tests for EnhancedCreatedEvent class."""

    def test_enhanced_event_creation(self):
        """Test that EnhancedCreatedEvent can be created with all fields."""
        event = EnhancedCreatedEvent(
            event_id="evt123",
            calendar_id="cal456",
            event_name="Test Event",
            start_time=dt.datetime(2024, 1, 15, 9, 0, 0),
            end_time=dt.datetime(2024, 1, 15, 10, 0, 0),
            created_at=dt.datetime.now(),
            batch_id="batch1",
            request_snapshot={"day_length_hours": 1},
        )

        assert event.event_id == "evt123"
        assert event.calendar_id == "cal456"
        assert event.event_name == "Test Event"
        assert event.request_snapshot["day_length_hours"] == 1

    def test_enhanced_event_timezone_preservation(self):
        """Test that event times preserve timezone info."""
        tz_aware_time = dt.datetime(
            2024, 6, 15, 14, 30, 0, tzinfo=dt.timezone(dt.timedelta(hours=2))
        )

        event = EnhancedCreatedEvent(
            event_id="event456",
            calendar_id="cal456",
            event_name="Timezone Test",
            start_time=tz_aware_time,
            end_time=tz_aware_time + dt.timedelta(hours=2),
            created_at=dt.datetime.now(),
            batch_id="batch2",
            request_snapshot={},
        )

        assert event.event_id == "event456"
        assert event.start_time.tzinfo is not None

    def test_event_serialization_roundtrip(self):
        """Test that events can be serialized and deserialized."""
        original = EnhancedCreatedEvent(
            event_id="serial-test",
            calendar_id="cal1",
            event_name="Serialization Test",
            start_time=dt.datetime(2024, 7, 15, 9, 0, 0),
            end_time=dt.datetime(2024, 7, 15, 17, 0, 0),
            created_at=dt.datetime.now(),
            batch_id="batch4",
            request_snapshot={"test": True},
        )

        # Serialize to dict
        data = {
            "event_id": original.event_id,
            "calendar_id": original.calendar_id,
            "event_name": original.event_name,
            "start_time": original.start_time.isoformat(),
            "end_time": original.end_time.isoformat(),
            "created_at": original.created_at.isoformat(),
            "batch_id": original.batch_id,
            "request_snapshot": original.request_snapshot,
        }

        # Deserialize back
        restored = EnhancedCreatedEvent(
            event_id=data["event_id"],
            calendar_id=data["calendar_id"],
            event_name=data["event_name"],
            start_time=dt.datetime.fromisoformat(data["start_time"]),
            end_time=dt.datetime.fromisoformat(data["end_time"]),
            created_at=dt.datetime.fromisoformat(data["created_at"]),
            batch_id=data["batch_id"],
            request_snapshot=data["request_snapshot"],
        )

        assert restored.event_id == original.event_id
        assert restored.start_time == original.start_time


class TestCreatedEvent:
    """Tests for CreatedEvent dataclass."""

    def test_created_event_creation(self):
        """Test that CreatedEvent can be created with required fields."""
        event = CreatedEvent(event_id="evt123", calendar_id="cal456")

        assert event.event_id == "evt123"
        assert event.calendar_id == "cal456"

    def test_created_event_equality(self):
        """Test that two CreatedEvents with same values are equal."""
        event1 = CreatedEvent(event_id="evt789", calendar_id="cal123")
        event2 = CreatedEvent(event_id="evt789", calendar_id="cal123")

        assert event1 == event2

    def test_created_event_inequality(self):
        """Test that two CreatedEvents with different values are not equal."""
        event1 = CreatedEvent(event_id="evt1", calendar_id="cal1")
        event2 = CreatedEvent(event_id="evt2", calendar_id="cal2")

        assert event1 != event2


class TestEventHelpers:
    """Tests for event-related helper functions."""

    def test_enhanced_from_created_event(self):
        """Test creating EnhancedCreatedEvent from CreatedEvent."""
        created = CreatedEvent(event_id="enhanced-test", calendar_id="cal1")

        enhanced = EnhancedCreatedEvent(
            event_id=created.event_id,
            calendar_id=created.calendar_id,
            event_name="Enhanced from Created",
            start_time=dt.datetime(2024, 1, 15, 9, 0, 0),
            end_time=dt.datetime(2024, 1, 15, 10, 0, 0),
            created_at=dt.datetime.now(),
            batch_id="batch-1",
            request_snapshot={},
        )

        assert enhanced.event_id == created.event_id
        assert enhanced.calendar_id == created.calendar_id
        assert enhanced.event_name == "Enhanced from Created"
