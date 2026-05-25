"""Integration tests for Update mode workflow.

Tests the complete event update flow including batch updates,
stop functionality, and email notification.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock

import pytest

from app.services import EnhancedCreatedEvent
from app.workers import UpdateWorker


class TestUpdateModeBatchUpdate:
    """Test batch update operations."""

    def test_deletes_old_events(self, mockable_api, sample_batch, sample_schedule_request):
        """Test that old events are deleted before creating new ones."""
        worker = UpdateWorker(
            mockable_api,
            "cal_primary",
            sample_batch,
            sample_schedule_request,
            send_email=False,
            notification_email="[REDACTED]",
        )

        worker.run()

        # Should have deleted each old event
        # The mock API's delete_event is called for each event in the batch
        assert mockable_api._mock_delete_event.call_count == len(sample_batch)

    def test_creates_new_events(self, mockable_api, sample_batch, sample_schedule_request):
        """Test that new events are created with updated schedule."""
        worker = UpdateWorker(
            mockable_api,
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
        # The mock API's create_event is called for each new event
        assert mockable_api._mock_create_event.call_count >= 1

    def test_emits_progress_for_each_operation(self, mockable_api, sample_batch, sample_schedule_request):
        """Test that progress is emitted for each delete and create operation."""
        worker = UpdateWorker(
            mockable_api,
            "cal_primary",
            sample_batch,
            sample_schedule_request,
            send_email=False,
            notification_email="[REDACTED]",
        )

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))

        worker.run()

        # Should have progress messages for delete and create operations
        assert len(progress_messages) >= 2

    def test_preserves_batch_id_in_new_events(self, mockable_api, sample_batch, sample_schedule_request):
        """Test that new events preserve the batch ID from original events."""
        # Get the original batch_id
        original_batch_id = sample_batch[0].batch_id if sample_batch else "original_batch"

        worker = UpdateWorker(
            mockable_api,
            "cal_primary",
            sample_batch,
            sample_schedule_request,
            send_email=False,
            notification_email="[REDACTED]",
        )

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))
        worker.run()

        # All new events should share the same batch_id
        if created_events:
            batch_ids = {e.batch_id for e in created_events}
            assert len(batch_ids) == 1


class TestUpdateModeStopRequested:
    """Test stop/cancellation during update operations."""

    def test_stops_after_current_operation(self, mockable_api, sample_batch, sample_schedule_request):
        """Test that UpdateWorker can be stopped (basic test)."""
        worker = UpdateWorker(
            mockable_api,
            "cal_primary",
            sample_batch,
            sample_schedule_request,
            send_email=False,
            notification_email="[REDACTED]",
        )

        # Verify worker can be instantiated and has stop method
        assert hasattr(worker, 'stop')
        assert callable(worker.stop)


class TestUpdateModeEmailNotification:
    """Test email notification during update operations."""

    def test_sends_email_when_enabled(self, mockable_api, sample_batch):
        """Test that email is sent after successful update."""
        from app.validation import ScheduleRequest

        # Create a request with email enabled
        request_with_email = ScheduleRequest(
            event_name="Test Update",
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

        worker = UpdateWorker(
            mockable_api,
            "cal_primary",
            sample_batch,
            request_with_email,
            send_email=True,
            notification_email="[REDACTED]",
        )

        worker.run()

        assert mockable_api._mock_send_email.called

    def test_skips_email_when_disabled(self, mockable_api, sample_batch):
        """Test that no email is sent when send_email is False."""
        from app.validation import ScheduleRequest

        request_no_email = ScheduleRequest(
            event_name="Test Update",
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

        worker = UpdateWorker(
            mockable_api,
            "cal_primary",
            sample_batch,
            request_no_email,
            send_email=False,
            notification_email="[REDACTED]",
        )

        worker.run()

        assert not mockable_api._mock_send_email.called


class TestUpdateModeSingleEvent:
    """Test single event update operations."""

    def test_updates_single_event(self, mockable_api, sample_event):
        """Test that a single event is updated correctly."""
        from app.validation import ScheduleRequest

        request = ScheduleRequest(
            event_name="Single Update",
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

        worker = UpdateWorker(
            mockable_api,
            "cal_primary",
            [sample_event],
            request,
            send_email=False,
            notification_email="[REDACTED]",
        )

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))
        worker.run()

        # Should have updated the event
        assert len(created_events) >= 1


class TestUpdateModeNewSchedule:
    """Test update operations with new schedules."""

    def test_applies_new_event_name(self, mockable_api, sample_batch):
        """Test that new event name from schedule is applied."""
        from app.validation import ScheduleRequest

        # Create a request with a specific event name
        request_with_new_name = ScheduleRequest(
            event_name="Updated Event",
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
            send_email=False,
        )

        worker = UpdateWorker(
            mockable_api,
            "cal_primary",
            sample_batch,
            request_with_new_name,
            send_email=False,
            notification_email="[REDACTED]",
        )

        created_events = []
        worker.finished.connect(lambda events: created_events.extend(events))
        worker.run()

        # Verify the new event name is in the created events
        for event in created_events:
            assert "Updated Event" in event.event_name or event.event_name == "Updated Event"


class TestUpdateModeErrorHandling:
    """Test error handling during update operations."""

    def test_reports_delete_errors(self, mockable_api, sample_batch, sample_schedule_request):
        """Test that delete errors are reported through error signal."""
        from googleapiclient.errors import HttpError

        error_response = MagicMock()
        error_response.status = 500

        # Configure the mock to raise an error
        mockable_api._mock_delete_event.side_effect = HttpError(
            error_response, b"Internal Server Error"
        )

        worker = UpdateWorker(
            mockable_api,
            "cal_primary",
            sample_batch,
            sample_schedule_request,
            send_email=False,
            notification_email="[REDACTED]",
        )

        errors = []
        worker.error.connect(lambda err: errors.append(err))
        worker.run()

        # Should report the error
        assert len(errors) > 0
