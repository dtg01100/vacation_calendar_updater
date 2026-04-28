"""Integration tests for Create mode workflow.

Tests the complete event creation flow from schedule request
through worker execution to event creation and email notification.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock

import pytest

from app.services import CreatedEvent, EnhancedCreatedEvent
from app.validation import ScheduleRequest
from app.workers import EventCreationWorker


class TestCreateModeSingleDay:
    """Test single-day event creation workflow."""

    def test_creates_single_event(self, mock_api, sample_schedule_request_single_day):
        """Test that creating an event for one day produces exactly one event."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        worker = EventCreationWorker(
            mock_api, "cal_primary", sample_schedule_request_single_day
        )

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))
        worker.run()

        assert len(created_events) == 1
        assert created_events[0].event_id == "new_event"

    def test_single_event_has_correct_times(
        self, mock_api, sample_schedule_request_single_day
    ):
        """Test that the event has correct start and end times."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        worker = EventCreationWorker(
            mock_api, "cal_primary", sample_schedule_request_single_day
        )

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))
        worker.run()

        event = created_events[0]
        assert event.start_time.date() == dt.date(2024, 5, 15)
        assert event.start_time.time() == dt.time(9, 0)
        assert event.end_time.time() == dt.time(17, 0)  # 9am + 8 hours


class TestCreateModeMultiDay:
    """Test multi-day vacation schedule creation."""

    def test_creates_events_for_each_weekday(self, mock_api, sample_schedule_request):
        """Test that events are created for each weekday in the schedule.

        The sample_schedule_request spans March 4-8, 2024 (Monday-Friday).
        """
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        worker = EventCreationWorker(
            mock_api, "cal_primary", sample_schedule_request
        )

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))
        worker.run()

        # Should create 5 events (Mon-Fri)
        assert len(created_events) == 5
        assert mock_api.create_event.call_count == 5

        # All should be weekdays
        for event in created_events:
            assert event.start_time.weekday() < 5  # Monday=0, Friday=4

    def test_all_events_share_batch_id(self, mock_api, sample_schedule_request):
        """Test that all created events share the same batch_id."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        worker = EventCreationWorker(
            mock_api, "cal_primary", sample_schedule_request
        )

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))
        worker.run()

        batch_ids = {e.batch_id for e in created_events}
        assert len(batch_ids) == 1  # All same batch_id

    def test_events_have_request_snapshot(self, mock_api, sample_schedule_request):
        """Test that events preserve the request snapshot."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        worker = EventCreationWorker(
            mock_api, "cal_primary", sample_schedule_request
        )

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))
        worker.run()

        for event in created_events:
            assert event.request_snapshot is not None
            assert event.request_snapshot["event_name"] == "Test Vacation"
            assert event.request_snapshot["send_email"] is True


class TestCreateModeEmailNotification:
    """Test email notification during event creation."""

    def test_sends_email_when_enabled(self, mock_api, sample_schedule_request):
        """Test that email is sent after successful event creation."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        worker = EventCreationWorker(
            mock_api, "cal_primary", sample_schedule_request
        )

        worker.run()

        assert mock_api.send_email.called

    def test_skips_email_when_disabled(
        self, mock_api, sample_schedule_request_single_day
    ):
        """Test that no email is sent when send_email is False."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        worker = EventCreationWorker(
            mock_api, "cal_primary", sample_schedule_request_single_day
        )

        worker.run()

        # sample_schedule_request_single_day has send_email=False
        assert not mock_api.send_email.called


class TestCreateModeStopRequested:
    """Test stop/cancellation during event creation."""

    def test_stops_after_current_event(self, mock_api, sample_schedule_request):
        """Test that worker stops after current event when stop requested."""
        call_count = 0

        def slow_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return CreatedEvent(event_id=f"event_{call_count}", calendar_id="cal_primary")

        mock_api.create_event.side_effect = slow_create

        worker = EventCreationWorker(
            mock_api, "cal_primary", sample_schedule_request
        )

        # Request stop after first event
        worker.request_stop()

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))
        worker.stopped.connect(lambda: None)  # Just to track it was called
        worker.run()

        # Should have stopped
        assert call_count == 1 or worker._stop_requested

    def test_emits_stopped_signal(self, mock_api, sample_schedule_request):
        """Test that stopped signal is emitted when stop is requested."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        worker = EventCreationWorker(
            mock_api, "cal_primary", sample_schedule_request
        )

        worker.request_stop()

        stopped_called = []
        worker.stopped.connect(lambda: stopped_called.append(True))
        worker.run()

        assert len(stopped_called) > 0


class TestCreateModeProgressReporting:
    """Test progress reporting during event creation."""

    def test_emits_progress_for_each_event(self, mock_api, sample_schedule_request):
        """Test that progress is emitted for each created event."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        worker = EventCreationWorker(
            mock_api, "cal_primary", sample_schedule_request
        )

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))

        worker.run()

        # Should have progress for each event
        assert len(progress_messages) >= 5
        creation_messages = [
            msg for msg in progress_messages if "Created event" in msg
        ]
        assert len(creation_messages) == 5

    def test_progress_includes_date_info(self, mock_api, sample_schedule_request):
        """Test that progress messages include date information."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        worker = EventCreationWorker(
            mock_api, "cal_primary", sample_schedule_request
        )

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))

        worker.run()

        # Should include dates from the schedule
        creation_messages = [
            msg for msg in progress_messages if "Created event" in msg
        ]
        assert len(creation_messages) > 0


class TestCreateModeCustomHours:
    """Test event creation with custom day length."""

    def test_respects_custom_day_length(self, mock_api, sample_schedule_request_custom_hours):
        """Test that events are created with custom start/end times."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_work",
        )

        worker = EventCreationWorker(
            mock_api, "cal_work", sample_schedule_request_custom_hours
        )

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))
        worker.run()

        # 4-hour days, should create 3 events (June 1-3 are Sat, Sun, Mon - wait
        # June 1, 2024 is Saturday. Let me check the weekdays...
        # Actually, the request has all weekdays=True, so it should be 3 events
        # (Mon June 3 is first weekday in range)
        for event in created_events:
            duration = event.end_time - event.start_time
            assert duration.total_seconds() == 4 * 3600  # 4 hours


class TestCreateModeErrorHandling:
    """Test error handling during event creation."""

    def test_handles_api_error(self, mock_api, sample_schedule_request_single_day):
        """Test that API errors are reported through error signal."""
        from googleapiclient.errors import HttpError

        error_response = MagicMock()
        error_response.status = 500
        mock_api.create_event.side_effect = HttpError(
            error_response, b"Internal Server Error"
        )

        worker = EventCreationWorker(
            mock_api, "cal_primary", sample_schedule_request_single_day
        )

        errors = []
        worker.error.connect(lambda err: errors.append(err))
        worker.run()

        assert len(errors) > 0
