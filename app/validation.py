from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Mapping, TYPE_CHECKING

from dateutil.parser import parse
from dateutil.rrule import DAILY, FR, MO, SA, SU, TH, TU, WE, rrule
import validate_email

if TYPE_CHECKING:
    from app.services import EnhancedCreatedEvent

try:  # Optional: allow validation to run without Qt, but normalize Qt types when available.
    from PySide6 import QtCore
except Exception:  # pragma: no cover - fallback when PySide6 not present
    QtCore = None

WEEKDAY_ORDER = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
WEEKDAY_CONST = {
    "monday": MO,
    "tuesday": TU,
    "wednesday": WE,
    "thursday": TH,
    "friday": FR,
    "saturday": SA,
    "sunday": SU,
}


@dataclass
class ScheduleRequest:
    event_name: str
    notification_email: str
    calendar_name: str
    start_date: dt.date
    end_date: dt.date
    start_time: dt.time
    day_length_hours: float
    weekdays: Mapping[str, bool]
    send_email: bool = True


@dataclass
class UndoBatch:
    batch_id: str
    created_at: dt.datetime
    events: list[EnhancedCreatedEvent]  # type: ignore[name-defined]
    description: str
    is_undone: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "batch_id": self.batch_id,
            "created_at": self.created_at.isoformat(),
            "events": [self._event_to_dict(event) for event in self.events],
            "description": self.description,
            "is_undone": self.is_undone,
        }

    @staticmethod
    def _event_to_dict(event) -> dict:
        """Convert EnhancedCreatedEvent to dictionary"""
        return {
            "event_id": event.event_id,
            "calendar_id": event.calendar_id,
            "event_name": event.event_name,
            "start_time": event.start_time.isoformat(),
            "end_time": event.end_time.isoformat(),
            "created_at": event.created_at.isoformat(),
            "batch_id": event.batch_id,
            "request_snapshot": event.request_snapshot,
        }

    @staticmethod
    def from_dict(data: dict) -> "UndoBatch":
        """Reconstruct UndoBatch from dictionary."""
        from .services import EnhancedCreatedEvent

        events = []
        for event_data in data.get("events", []):
            event = EnhancedCreatedEvent(
                event_id=event_data["event_id"],
                calendar_id=event_data["calendar_id"],
                event_name=event_data["event_name"],
                start_time=parse_datetime(event_data["start_time"]),
                end_time=parse_datetime(event_data["end_time"]),
                created_at=parse_datetime(event_data["created_at"]),
                batch_id=event_data["batch_id"],
                request_snapshot=event_data.get("request_snapshot", {}),
            )
            events.append(event)

        return UndoBatch(
            batch_id=data["batch_id"],
            created_at=parse_datetime(data["created_at"]),
            events=events,
            description=data["description"],
            is_undone=data.get("is_undone", False),
        )


def parse_date(value) -> dt.date:
    """Normalize supported date inputs to a python date.

    Accepts:
    - datetime.date (returned as-is)
    - PySide6.QtCore.QDate (converted via toPython)
    - str (parsed leniently via dateutil)
    """

    if isinstance(value, dt.date):
        return value
    if QtCore and isinstance(value, QtCore.QDate):  # type: ignore[attr-defined]
        if not value.isValid():
            raise ValueError("invalid QDate")
        return value.toPython()
    if isinstance(value, str):
        return parse(value).date()
    raise TypeError(f"Unsupported date type: {type(value)!r}")


def parse_time(value) -> dt.time:
    """Normalize supported time inputs to a python time (seconds/micros zeroed).

    Accepts:
    - datetime.time (returned as-is)
    - PySide6.QtCore.QTime (converted via toPython)
    - str (parses HHmm or HH:mm)
    """

    if isinstance(value, dt.time):
        return value.replace(second=0, microsecond=0)
    if QtCore and isinstance(value, QtCore.QTime):  # type: ignore[attr-defined]
        if not value.isValid():
            raise ValueError("invalid QTime")
        return value.toPython().replace(second=0, microsecond=0)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("time is empty")
        if ":" not in cleaned and len(cleaned) in (3, 4):  # allow HHmm without colon
            cleaned = cleaned[:-2] + ":" + cleaned[-2:]
        parsed = parse(cleaned)
        return parsed.time().replace(second=0, microsecond=0)
    raise TypeError(f"Unsupported time type: {type(value)!r}")


def parse_datetime(value) -> dt.datetime:
    """Normalize supported datetime inputs to a python datetime.

    Accepts:
    - datetime.datetime (returned as-is)
    - str (parsed via dateutil)
    """
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, str):
        return parse(value)
    raise TypeError(f"Unsupported datetime type: {type(value)!r}")


def weekday_constants(weekdays: Mapping[str, bool]) -> list:
    return [WEEKDAY_CONST[key] for key in WEEKDAY_ORDER if weekdays.get(key, False)]


def build_schedule(req: ScheduleRequest) -> list[tuple[dt.datetime, dt.datetime]]:
    weekday_list = weekday_constants(req.weekdays)
    if not weekday_list:
        return []
    start_dt = dt.datetime.combine(req.start_date, req.start_time)
    end_dt = dt.datetime.combine(req.end_date, req.start_time)
    end_increment = dt.timedelta(hours=req.day_length_hours)

    start_list = list(rrule(DAILY, byweekday=tuple(weekday_list), dtstart=start_dt, until=end_dt))
    stop_list = [s + end_increment for s in start_list]
    return list(zip(start_list, stop_list))


def validate_request(req: ScheduleRequest) -> list[str]:
    errors: list[str] = []
    if not req.event_name.strip():
        errors.append("Event name is required")
    if not validate_email.validate_email(req.notification_email):
        errors.append("Notification email is invalid")
    weekday_list = weekday_constants(req.weekdays)
    if not weekday_list:
        errors.append("Select at least one weekday")
    if req.day_length_hours <= 0 or req.day_length_hours >= 24:
        errors.append("Day length must be between 0 and 24 hours")
    if req.start_date > req.end_date:
        errors.append("Start date must be on or before end date")
    if req.calendar_name.strip() == "":
        errors.append("Calendar selection is required")

    schedule = build_schedule(req)
    if not schedule:
        errors.append("No working days in range")
    return errors
