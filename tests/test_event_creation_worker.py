"""Tests for EventCreationWorker.

Tests focus on critical paths: event creation flow, stop/cancellation, 
signal emissions, error handling, and email notifications.
"""

import datetime as dt
from unittest.mock import MagicMock

import pytest

from app.services import CreatedEvent, EnhancedCreatedEvent
from app.validation import ScheduleRequest
from app.workers import EventCreationWorker


@pytest.fixture
def mock_api():
    """Create a mock GoogleApi."""
    api = MagicMock()
    api.create_event = MagicMock()
    api.send_email = MagicMock()
    return api


@pytest.fixture
def sample_schedule_request():
    """Create a sample schedule request."""
    return ScheduleRequest(
        event_name="Test Vacation",
        notification_email="test@example.com",
        calendar_name="Work Calendar",
        # Use a full Monday-Friday workweek to exercise weekday scheduling
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


class TestEventCreationWorkerInit:
    """Test EventCreationWorker initialization."""

    def test_initialization(self, mock_api, sample_schedule_request):
        """Test worker initializes with correct attributes."""
        worker = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        assert worker.api == mock_api
        assert worker.calendar_id == "cal_123"
        assert worker.request == sample_schedule_request
        assert worker._stop_requested is False
        assert worker.batch_id is not None
        assert len(worker.batch_id) > 0

    def test_has_required_signals(self, mock_api, sample_schedule_request):
        """Test worker has finished, stopped, progress, and error signals."""
        worker = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        assert hasattr(worker, "finished")
        assert hasattr(worker, "stopped")
        assert hasattr(worker, "progress")
        assert hasattr(worker, "error")

    def test_unique_batch_ids(self, mock_api, sample_schedule_request):
        """Test that each worker gets a unique batch_id."""
        worker1 = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )
        worker2 = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        assert worker1.batch_id != worker2.batch_id


class TestEventCreationExecution:
    """Test event creation execution."""

    def test_creates_events_for_schedule(self, mock_api, sample_schedule_request):
        """Test worker creates events for all dates in schedule."""
        # Mock API to return created events
        mock_api.create_event.return_value = CreatedEvent(
            event_id="event_123",
            calendar_id="cal_123"
        )

        worker = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        # Capture finished signal
        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))

        worker.run()

        # Should create 5 events (Monday-Friday, Mar 4-8, 2024)
        assert len(created_events) == 5
        assert all(isinstance(e, EnhancedCreatedEvent) for e in created_events)
        assert mock_api.create_event.call_count == 5

    def test_created_events_have_correct_structure(self, mock_api, sample_schedule_request):
        """Test created events have all required fields."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="event_123",
            calendar_id="cal_123"
        )

        worker = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))

        worker.run()

        for event in created_events:
            assert event.event_id is not None
            assert event.calendar_id == "cal_123"
            assert event.event_name == "Test Vacation"
            assert event.batch_id == worker.batch_id
            assert event.request_snapshot is not None
            assert event.created_at is not None

    def test_request_snapshot_preserved(self, mock_api, sample_schedule_request):
        """Test that request snapshot contains all request data."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="event_123",
            calendar_id="cal_123"
        )

        worker = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))

        worker.run()

        snapshot = created_events[0].request_snapshot
        assert snapshot["event_name"] == "Test Vacation"
        assert snapshot["notification_email"] == "test@example.com"
        assert snapshot["calendar_name"] == "Work Calendar"
        assert snapshot["day_length_hours"] == 8.0
        assert "weekdays" in snapshot
        assert snapshot["send_email"] is True

    def test_events_have_correct_times(self, mock_api, sample_schedule_request):
        """Test events are created with correct start/end times."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="event_123",
            calendar_id="cal_123"
        )

        worker = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))

        worker.run()

        # Check first event
        first_event = created_events[0]
        assert first_event.start_time.time() == dt.time(9, 0)
        assert first_event.end_time.time() == dt.time(17, 0)  # 9am + 8 hours
        
        # Check all events are on weekdays
        for event in created_events:
            assert event.start_time.weekday() < 5  # Monday=0, Friday=4


class TestEventCreationProgress:
    """Test progress reporting during event creation."""

    def test_emits_progress_for_each_event(self, mock_api, sample_schedule_request):
        """Test worker emits progress signal for each created event."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="event_123",
            calendar_id="cal_123"
        )

        worker = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))

        worker.run()

        # Should have progress for each event + email notification
        assert len(progress_messages) >= 5
        assert any("Created event" in msg for msg in progress_messages)

    def test_progress_includes_date_and_time(self, mock_api, sample_schedule_request):
        """Test progress messages include date and time information."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="event_123",
            calendar_id="cal_123"
        )

        worker = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))

        worker.run()

        # Check that progress messages contain date/time info
        creation_messages = [msg for msg in progress_messages if "Created event" in msg]
        assert any("2024-03-04" in msg for msg in creation_messages)
        assert any("09:00:00" in msg for msg in creation_messages)


class TestEventCreationEmailNotification:
    """Test email notification functionality."""

    def test_sends_email_when_enabled(self, mock_api, sample_schedule_request):
        """Test email is sent when send_email is True."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="event_123",
            calendar_id="cal_123"
        )

        sample_schedule_request.send_email = True
        worker = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        worker.run()

        mock_api.send_email.assert_called_once()
        call_args = mock_api.send_email.call_args
        assert call_args[0][0] == "test@example.com"  # recipient
        assert "Test Vacation" in call_args[0][1]  # subject
        assert "enabled" in call_args[1]
        assert call_args[1]["enabled"] is True

    def test_no_email_when_disabled(self, mock_api, sample_schedule_request):
        """Test email is not sent when send_email is False."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="event_123",
            calendar_id="cal_123"
        )

        sample_schedule_request.send_email = False
        worker = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        worker.run()

        # send_email should still be called but with enabled=False
        call_args = mock_api.send_email.call_args
        assert call_args[1]["enabled"] is False

    def test_email_contains_event_summary(self, mock_api, sample_schedule_request):
        """Test email contains summary of created events."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="event_123",
            calendar_id="cal_123"
        )

        worker = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        worker.run()

        call_args = mock_api.send_email.call_args
        email_body = call_args[0][2]  # body is 3rd positional arg
        
        assert "Test Vacation" in email_body
        assert "40" in email_body or "40.0" in email_body  # 5 days * 8 hours
        assert "5 days" in email_body
        assert "2024-03-04" in email_body
        assert "2024-03-08" in email_body


class TestEventCreationStopHandling:
    """Test stop/cancellation functionality."""

    def test_stop_method_sets_flag(self, mock_api, sample_schedule_request):
        """Test stop() method sets the stop flag."""
        worker = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        assert worker._stop_requested is False
        worker.stop()
        assert worker._stop_requested is True

    def test_stops_before_completion(self, mock_api, sample_schedule_request):
        """Test worker stops when stop is requested mid-execution."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="event_123",
            calendar_id="cal_123"
        )

        worker = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        # Set up to stop after first event
        call_count = [0]
        def create_and_stop(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                worker.stop()
            return CreatedEvent(event_id="event_123", calendar_id="cal_123")

        mock_api.create_event.side_effect = create_and_stop

        stopped_emitted = []
        worker.stopped.connect(lambda: stopped_emitted.append(True))

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))

        worker.run()

        # Should have stopped early
        assert len(stopped_emitted) == 1
        assert len(created_events) == 0  # finished not emitted when stopped

    def test_emits_stopped_signal(self, mock_api, sample_schedule_request):
        """Test stopped signal is emitted when stopping."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="event_123",
            calendar_id="cal_123"
        )

        worker = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        # Stop immediately
        worker.stop()

        stopped_emitted = []
        worker.stopped.connect(lambda: stopped_emitted.append(True))

        worker.run()

        assert len(stopped_emitted) == 1


class TestEventCreationErrorHandling:
    """Test error handling during event creation."""

    def test_emits_error_on_api_failure(self, mock_api, sample_schedule_request):
        """Test error signal is emitted when API call fails."""
        mock_api.create_event.side_effect = Exception("API Error")

        worker = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        error_messages = []
        worker.error.connect(lambda msg: error_messages.append(msg))

        worker.run()

        assert len(error_messages) == 1
        assert "API Error" in error_messages[0]

    def test_no_finished_signal_on_error(self, mock_api, sample_schedule_request):
        """Test finished signal is not emitted when error occurs."""
        mock_api.create_event.side_effect = Exception("API Error")

        worker = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        finished_called = []
        worker.finished.connect(lambda events: finished_called.append(events))

        worker.run()

        assert len(finished_called) == 0

    def test_handles_email_sending_failure(self, mock_api, sample_schedule_request):
        """Test worker continues when email sending fails."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="event_123",
            calendar_id="cal_123"
        )
        mock_api.send_email.side_effect = Exception("Email failed")

        worker = EventCreationWorker(
            mock_api, "cal_123", sample_schedule_request
        )

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))

        worker.run()

        # Events should still be created despite email failure
        assert len(created_events) == 5
        # Should have progress message about email failure
        assert any("Email notification failed" in msg for msg in progress_messages)


class TestEventCreationEdgeCases:
    """Test edge cases in event creation."""

    def test_handles_empty_schedule(self, mock_api):
        """Test worker handles schedule with no working days."""
        # Request with no weekdays selected
        request = ScheduleRequest(
            event_name="Test",
            notification_email="test@example.com",
            calendar_name="Work",
            start_date=dt.date(2024, 3, 1),
            end_date=dt.date(2024, 3, 5),
            start_time=dt.time(9, 0),
            day_length_hours=8.0,
            weekdays={
                "monday": False,
                "tuesday": False,
                "wednesday": False,
                "thursday": False,
                "friday": False,
                "saturday": False,
                "sunday": False,
            },
            send_email=False,
        )

        worker = EventCreationWorker(mock_api, "cal_123", request)

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))

        worker.run()

        # Should complete with zero events
        assert len(created_events) == 0
        assert mock_api.create_event.call_count == 0

    def test_handles_single_day_schedule(self, mock_api):
        """Test worker handles schedule with single day."""
        request = ScheduleRequest(
            event_name="Single Day",
            notification_email="test@example.com",
            calendar_name="Work",
            start_date=dt.date(2024, 3, 1),
            end_date=dt.date(2024, 3, 1),  # Same day
            start_time=dt.time(9, 0),
            day_length_hours=8.0,
            weekdays={"monday": True, "tuesday": False, "wednesday": False,
                     "thursday": False, "friday": True, "saturday": False,
                     "sunday": False},
            send_email=False,
        )

        mock_api.create_event.return_value = CreatedEvent(
            event_id="event_123",
            calendar_id="cal_123"
        )

        worker = EventCreationWorker(mock_api, "cal_123", request)

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))

        worker.run()

        assert len(created_events) == 1

    def test_handles_weekend_only_schedule(self, mock_api):
        """Test worker creates events for weekend days when selected."""
        request = ScheduleRequest(
            event_name="Weekend Work",
            notification_email="test@example.com",
            calendar_name="Work",
            start_date=dt.date(2024, 3, 2),  # Saturday
            end_date=dt.date(2024, 3, 3),    # Sunday
            start_time=dt.time(9, 0),
            day_length_hours=4.0,
            weekdays={"monday": False, "tuesday": False, "wednesday": False,
                     "thursday": False, "friday": False, "saturday": True,
                     "sunday": True},
            send_email=False,
        )

        mock_api.create_event.return_value = CreatedEvent(
            event_id="event_123",
            calendar_id="cal_123"
        )

        worker = EventCreationWorker(mock_api, "cal_123", request)

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))

        worker.run()

        assert len(created_events) == 2
        # Verify they're actually weekend days
        assert all(e.start_time.weekday() >= 5 for e in created_events)
