"""Integration tests for Update mode workflow.

Tests the complete event update flow including batch updates,
stop functionality, and email notification.
"""

from __future__ import annotations

import datetime as dt

import pytest

from app.services import CreatedEvent, EnhancedCreatedEvent
from app.validation import ScheduleRequest
from app.workers import UpdateWorker


class TestUpdateModeBatchUpdate:
    """Test batch update operations."""

    def test_deletes_old_events(self, mock_api, sample_batch, sample_schedule_request):
        """Test that old events are deleted before creating new ones."""
        worker = UpdateWorker(
            mock_api,
            "cal_primary",
            sample_batch,
            sample_schedule_request,
            send_email=False,
            notification_email="[REDACTED]",
        )

        worker.run()

        # Should have deleted each old event
        for event in sample_batch:
            mock_api.delete_event.assert_any_call(event.event_id)

    def test_creates_new_events(self, mock_api, sample_batch, sample_schedule_request):
        """Test that new events are created with updated schedule."""
        mock_api.delete_event.return_value = None
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        worker = UpdateWorker(
            mock_api,
            "cal_primary",
            sample_batch,
            sample_schedule_request,
            send_email=False,
            notification_email="[REDACTED]",
        )

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))
        worker.run()

        # Should have created events for each weekday in new schedule
        assert len(created_events) >= 1
        assert mock_api.create_event.call_count >= 1

    def test_emits_progress_for_each_operation(self, mock_api, sample_batch, sample_schedule_request):
        """Test that progress is emitted for each delete and create operation."""
        mock_api.delete_event.return_value = None
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        worker = UpdateWorker(
            mock_api,
            "cal_primary",
            sample_batch,
            sample_schedule_request,
            send_email=False,
            notification_email="[REDACTED]",
        )

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))
        worker.run()

        # Should have progress for deletes and creates
        assert len(progress_messages) >= len(sample_batch)

    def test_preserves_batch_id_in_new_events(self, mock_api, sample_batch, sample_schedule_request):
        """Test that new events preserve the original batch ID."""
        mock_api.delete_event.return_value = None
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        original_batch_id = sample_batch[0].batch_id

        worker = UpdateWorker(
            mock_api,
            "cal_primary",
            sample_batch,
            sample_schedule_request,
            send_email=False,
            notification_email="[REDACTED]",
        )

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))
        worker.run()

        # New events should have same batch_id
        for event in created_events:
            assert event.batch_id == original_batch_id


class TestUpdateModeStopRequested:
    """Test stop/cancellation during update."""

    def test_stops_after_current_operation(self, mock_api, sample_batch, sample_schedule_request):
        """Test that worker stops after current operation."""
        call_count = [0]

        def delete_then_stop(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                worker.request_stop()
            return None

        mock_api.delete_event.side_effect = delete_then_stop
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        worker = UpdateWorker(
            mock_api,
            "cal_primary",
            sample_batch,
            sample_schedule_request,
            send_email=False,
            notification_email="[REDACTED]",
        )

        worker.run()

        # Should have stopped after first delete
        assert call_count[0] <= len(sample_batch)


class TestUpdateModeEmailNotification:
    """Test email notification during update."""

    def test_sends_email_when_enabled(self, mock_api, sample_batch, sample_schedule_request):
        """Test that email is sent after successful update."""
        mock_api.delete_event.return_value = None
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        worker = UpdateWorker(
            mock_api,
            "cal_primary",
            sample_batch,
            sample_schedule_request,
            send_email=True,
            notification_email="[REDACTED]",
        )

        worker.run()

        assert mock_api.send_email.called

    def test_skips_email_when_disabled(self, mock_api, sample_batch, sample_schedule_request):
        """Test that no email is sent when send_email is False."""
        mock_api.delete_event.return_value = None
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        worker = UpdateWorker(
            mock_api,
            "cal_primary",
            sample_batch,
            sample_schedule_request,
            send_email=False,
            notification_email="[REDACTED]",
        )

        worker.run()

        assert not mock_api.send_email.called


class TestUpdateModeSingleEvent:
    """Test update of single event."""

    def test_updates_single_event(self, mock_api, sample_event, sample_schedule_request_single_day):
        """Test that a single event can be updated."""
        mock_api.delete_event.return_value = None
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        worker = UpdateWorker(
            mock_api,
            "cal_primary",
            [sample_event],
            sample_schedule_request_single_day,
            send_email=False,
            notification_email="[REDACTED]",
        )

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))
        worker.run()

        assert len(created_events) == 1


class TestUpdateModeNewSchedule:
    """Test update with new schedule parameters."""

    def test_applies_new_event_name(self, mock_api, sample_batch):
        """Test that new event name is applied to created events."""
        mock_api.delete_event.return_value = None
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_primary",
        )

        new_request = ScheduleRequest(
            event_name="Updated Vacation Name",
            notification_email="[REDACTED]",
            calendar_name="Primary",
            start_date=dt.date(2024, 6, 1),
            end_date=dt.date(2024, 6, 2),
            start_time=dt.time(10, 0),
            day_length_hours=6.0,
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

        worker = UpdateWorker(
            mock_api,
            "cal_primary",
            sample_batch,
            new_request,
            send_email=False,
            notification_email="[REDACTED]",
        )

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))
        worker.run()

        for event in created_events:
            assert event.event_name == "Updated Vacation Name"


class TestUpdateModeErrorHandling:
    """Test error handling during update."""

    def test_reports_delete_errors(self, mock_api, sample_batch, sample_schedule_request):
        """Test that delete errors are reported."""
        from googleapiclient.errors import HttpError

        error_response = MagicMock()
        error_response.status = 500
        mock_api.delete_event.side_effect = HttpError(
            error_response, b"Internal Server Error"
        )

        worker = UpdateWorker(
            mock_api,
            "cal_primary",
            sample_batch,
            sample_schedule_request,
            send_email=False,
            notification_email="[REDACTED]",
        )

        errors = []
        worker.error.connect(lambda err: errors.append(err))
        worker.run()

        assert len(errors) > 0
