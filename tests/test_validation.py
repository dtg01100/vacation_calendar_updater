import datetime as dt

import pytest

from app.validation import ScheduleRequest, build_schedule, parse_date, parse_time, validate_request


def _req(**overrides):
    base = dict(
        event_name="Vacation",
        notification_email="user@example.com",
        calendar_name="Test",
        start_date=dt.date(2024, 1, 1),
        end_date=dt.date(2024, 1, 5),
        start_time=dt.time(8, 0),
        day_length_hours=8.0,
        weekdays={"monday": True, "tuesday": True, "wednesday": True, "thursday": True, "friday": True, "saturday": False, "sunday": False},
        send_email=True,
    )
    base.update(overrides)
    return ScheduleRequest(**base)


def test_build_schedule_counts_weekdays():
    req = _req()
    schedule = build_schedule(req)
    assert len(schedule) == 5
    assert schedule[0][0].date() == dt.date(2024, 1, 1)


def test_validate_request_rejects_invalid_email():
    req = _req(notification_email="not-an-email")
    errors = validate_request(req)
    assert any("email" in err.lower() for err in errors)


def test_validate_request_requires_weekday():
    req = _req(weekdays={day: False for day in req_weekdays()})
    errors = validate_request(req)
    assert any("weekday" in err.lower() for err in errors)


def test_parse_helpers_accept_multiple_formats():
    assert parse_date("2024-01-02").isoformat() == "2024-01-02"
    assert parse_time("0800").hour == 8
    assert parse_time("08:30").minute == 30


def req_weekdays():
    return ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
