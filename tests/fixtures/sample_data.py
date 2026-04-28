"""Sample data fixtures for testing."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

import pytest

from app.services import EnhancedCreatedEvent
from app.validation import ScheduleRequest


def make_event_id() -> str:
    """Generate a unique event ID."""
    return f"evt_{uuid.uuid4().hex[:8]}"


def make_batch_id() -> str:
    """Generate a unique batch ID."""
    return f"batch_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def sample_event() -> EnhancedCreatedEvent:
    """Create a single sample EnhancedCreatedEvent."""
    return EnhancedCreatedEvent(
        event_id=make_event_id(),
        calendar_id="cal_primary",
        event_name="Sample Vacation Day",
        start_time=dt.datetime(2024, 6, 15, 9, 0),
        end_time=dt.datetime(2024, 6, 15, 17, 0),
        created_at=dt.datetime.now(),
        batch_id=make_batch_id(),
        request_snapshot={
            "event_name": "Sample Vacation Day",
            "notification_email": "[REDACTED]",
            "calendar_name": "Primary",
            "start_time": "09:00",
            "day_length_hours": 8.0,
            "weekdays": {
                "monday": True,
                "tuesday": True,
                "wednesday": True,
                "thursday": True,
                "friday": True,
                "saturday": False,
                "sunday": False,
            },
            "send_email": True,
        },
    )


@pytest.fixture
def sample_batch() -> list[EnhancedCreatedEvent]:
    """Create a batch of 5 EnhancedCreatedEvents sharing a batch_id."""
    batch_id = make_batch_id()
    start_date = dt.date(2024, 7, 1)

    events = []
    for i in range(5):
        events.append(
            EnhancedCreatedEvent(
                event_id=make_event_id(),
                calendar_id="cal_primary",
                event_name=f"Vacation Day {i + 1}",
                start_time=dt.datetime(2024, 7, 1 + i, 9, 0),
                end_time=dt.datetime(2024, 7, 1 + i, 17, 0),
                created_at=dt.datetime.now(),
                batch_id=batch_id,
                request_snapshot={
                    "event_name": f"Vacation Day {i + 1}",
                    "notification_email": "[REDACTED]",
                    "calendar_name": "Primary",
                    "start_time": "09:00",
                    "day_length_hours": 8.0,
                    "weekdays": {
                        "monday": True,
                        "tuesday": True,
                        "wednesday": True,
                        "thursday": True,
                        "friday": True,
                        "saturday": False,
                        "sunday": False,
                    },
                    "send_email": True,
                },
            )
        )
    return events


@pytest.fixture
def sample_schedule_request() -> ScheduleRequest:
    """Create a sample ScheduleRequest for testing."""
    return ScheduleRequest(
        event_name="Test Vacation",
        notification_email="[REDACTED]",
        calendar_name="Primary",
        start_date=dt.date(2024, 3, 4),
        end_date=dt.date(2024, 3, 8),
        start_time=dt.time(9, 0),
        day_length_hours=8.0,
        weekdays={
            "monday": True,
            "tuesday": True,
            "wednesday": True,
            "thursday": True,
            "friday": True,
            "saturday": False,
            "sunday": False,
        },
        send_email=True,
    )


@pytest.fixture
def sample_schedule_request_single_day() -> ScheduleRequest:
    """Create a ScheduleRequest for a single day."""
    return ScheduleRequest(
        event_name="Single Day Off",
        notification_email="[REDACTED]",
        calendar_name="Primary",
        start_date=dt.date(2024, 5, 15),
        end_date=dt.date(2024, 5, 15),
        start_time=dt.time(9, 0),
        day_length_hours=8.0,
        weekdays={
            "monday": True,
            "tuesday": True,
            "wednesday": True,
            "thursday": True,
            "friday": True,
            "saturday": False,
            "sunday": False,
        },
        send_email=False,
    )


@pytest.fixture
def sample_schedule_request_custom_hours() -> ScheduleRequest:
    """Create a ScheduleRequest with custom day length."""
    return ScheduleRequest(
        event_name="Half Day Vacation",
        notification_email="[REDACTED]",
        calendar_name="Work Calendar",
        start_date=dt.date(2024, 6, 1),
        end_date=dt.date(2024, 6, 3),
        start_time=dt.time(8, 0),
        day_length_hours=4.0,
        weekdays={
            "monday": True,
            "tuesday": True,
            "wednesday": True,
            "thursday": True,
            "friday": True,
            "saturday": False,
            "sunday": False,
        },
        send_email=True,
    )