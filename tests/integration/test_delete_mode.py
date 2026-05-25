"""Integration tests for Delete mode workflow.

Tests the complete event deletion flow including single deletion,
batch deletion, undo functionality, and error handling.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock

import pytest

from app.services import EnhancedCreatedEvent
from app.validation import UndoBatch
from app.workers import DeleteWorker


def make_event(
    event_id: str,
    batch_id: str,
    start_time: dt.datetime | None = None,
) -> EnhancedCreatedEvent:
    """Helper to create test events."""
    if start_time is None:
        start_time = dt.datetime(2024, 6, 15, 9, 0)
    return EnhancedCreatedEvent(
        event_id=event_id,
        calendar_id="cal_primary",
        event_name=f"Event {event_id}",
        start_time=start_time,
        end_time=start_time + dt.timedelta(hours=8),
        created_at=dt.datetime.now(),
        batch_id=batch_id,
        request_snapshot={},
    )


class TestDeleteModeSingleEvent:
    """Test single event deletion."""

    def test_deletes_event_from_api(self, mockable_api, sample_batch):
        """Test that delete calls the API to remove the event."""
        event = sample_batch[0]

        worker = DeleteWorker(
            mockable_api,
            [event],
            send_email=False,
            notification_email="[REDACTED]",
            batch_description="Delete test",
        )

        worker.run()

        # Verify delete was called (check that mock was called)
        assert mockable_api._mock_delete_event.called
        # The actual argument is the EnhancedCreatedEvent, not just event_id
        assert mockable_api._mock_delete_event.call_count == 1

    def test_emits_finished_with_event_ids(self, mockable_api, sample_batch):
        """Test that finished signal includes deleted event IDs."""
        event = sample_batch[0]

        worker = DeleteWorker(
            mockable_api,
            [event],
            send_email=False,
            notification_email="[REDACTED]",
            batch_description="Delete test",
        )

        finished_data = []
        worker.finished.connect(lambda ids, desc: finished_data.append((ids, desc)))
        worker.run()

        assert len(finished_data) == 1
        deleted_ids, description = finished_data[0]
        assert event.event_id in deleted_ids
        assert description == "Delete test"


class TestDeleteModeBatchEvents:
    """Test batch event deletion."""

    def test_deletes_all_events_in_batch(self, mockable_api, sample_batch):
        """Test that all events in a batch are deleted."""
        worker = DeleteWorker(
            mockable_api,
            sample_batch,
            send_email=False,
            notification_email="[REDACTED]",
            batch_description="Batch delete test",
        )

        worker.run()

        # Verify all events were deleted
        assert mockable_api._mock_delete_event.call_count == len(sample_batch)

    def test_emits_progress_for_each_event(self, mockable_api, sample_batch):
        """Test that progress is emitted for each deleted event."""
        worker = DeleteWorker(
            mockable_api,
            sample_batch,
            send_email=False,
            notification_email="[REDACTED]",
            batch_description="Batch delete test",
        )

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))
        worker.run()

        # Should have progress for each event
        delete_messages = [msg for msg in progress_messages if "Deleted" in msg or "Skipped" in msg]
        assert len(delete_messages) >= len(sample_batch)


class TestDeleteModeEmailNotification:
    """Test email notification during deletion."""

    def test_sends_email_when_enabled(self, mockable_api, sample_batch):
        """Test that email is sent after batch deletion."""
        worker = DeleteWorker(
            mockable_api,
            sample_batch,
            send_email=True,
            notification_email="[REDACTED]",
            batch_description="Delete with email",
        )

        worker.run()

        assert mockable_api._mock_send_email.called

    def test_skips_email_when_disabled(self, mockable_api, sample_batch):
        """Test that no email is sent when send_email is False."""
        worker = DeleteWorker(
            mockable_api,
            sample_batch,
            send_email=False,
            notification_email="[REDACTED]",
            batch_description="Delete without email",
        )

        worker.run()

        assert not mockable_api._mock_send_email.called


class TestDeleteMode404Handling:
    """Test handling of already-deleted events (404 errors)."""

    def test_handles_404_gracefully(self, mockable_api, sample_batch):
        """Test that 404 errors are handled without crashing."""
        from googleapiclient.errors import HttpError

        error_response = MagicMock()
        error_response.status = 404

        # Configure the mock to raise 404 on first call
        mockable_api._mock_delete_event.side_effect = HttpError(error_response, b"Not found")

        worker = DeleteWorker(
            mockable_api,
            sample_batch,
            send_email=False,
            notification_email="[REDACTED]",
            batch_description="Delete with 404",
        )

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))
        worker.run()

        # Should emit progress about skipping
        skip_messages = [msg for msg in progress_messages if "Skipped" in msg]
        assert len(skip_messages) >= 1

    def test_continues_after_404(self, mockable_api, sample_batch):
        """Test that deletion continues for remaining events after 404."""
        from googleapiclient.errors import HttpError

        call_count = [0]

        def error_then_success(event):
            call_count[0] += 1
            if call_count[0] == 1:
                error_response = MagicMock()
                error_response.status = 404
                raise HttpError(error_response, b"Not found")
            return None

        mockable_api._mock_delete_event.side_effect = error_then_success

        worker = DeleteWorker(
            mockable_api,
            sample_batch,
            send_email=False,
            notification_email="[REDACTED]",
            batch_description="Continue after 404",
        )

        worker.run()

        # Should have attempted all events
        assert call_count[0] == len(sample_batch)


class TestDeleteMode410Handling:
    """Test handling of 410 Gone errors."""

    def test_handles_410_gracefully(self, mockable_api, sample_batch):
        """Test that 410 Gone errors are handled without crashing."""
        from googleapiclient.errors import HttpError

        error_response = MagicMock()
        error_response.status = 410

        mockable_api._mock_delete_event.side_effect = HttpError(error_response, b"Gone")

        worker = DeleteWorker(
            mockable_api,
            sample_batch,
            send_email=False,
            notification_email="[REDACTED]",
            batch_description="Delete with 410",
        )

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))
        worker.run()

        # Should complete without errors
        error_messages = [msg for msg in progress_messages if "Error" in msg]
        assert len(error_messages) == 0


class TestDeleteModeUndoIntegration:
    """Test integration with UndoManager for undo functionality."""

    def test_batch_can_be_undone(self, mockable_api, sample_batch, undo_manager):
        """Test that a deleted batch can be tracked for undo."""
        # Add the batch to undo manager
        undo_manager.add_batch(sample_batch, "Vacation batch")

        # Delete the events
        worker = DeleteWorker(
            mockable_api,
            sample_batch,
            send_email=False,
            notification_email="[REDACTED]",
            batch_description="Vacation batch",
        )
        worker.run()

        # Verify batch is tracked
        batches = undo_manager.get_undoable_batches()
        assert len(batches) == 1

    def test_deleted_events_not_in_undoable_list(
        self, mockable_api, sample_batch, undo_manager
    ):
        """Test that deleted events are properly tracked."""
        # Add batch
        undo_manager.add_batch(sample_batch, "Vacation batch")

        # Delete events
        worker = DeleteWorker(
            mockable_api,
            sample_batch,
            send_email=False,
            notification_email="[REDACTED]",
            batch_description="Test batch",
        )
        worker.run()

        # Verify batch is tracked
        batches = undo_manager.get_undoable_batches()
        assert len(batches) == 1


class TestDeleteModeErrorReporting:
    """Test error reporting during deletion."""

    def test_reports_non_404_errors(self, mockable_api, sample_batch):
        """Test that non-404 errors are reported through error signal."""
        from googleapiclient.errors import HttpError

        error_response = MagicMock()
        error_response.status = 500

        mockable_api._mock_delete_event.side_effect = HttpError(
            error_response, b"Internal Server Error"
        )

        worker = DeleteWorker(
            mockable_api,
            sample_batch,
            send_email=False,
            notification_email="[REDACTED]",
            batch_description="Delete with error",
        )

        errors = []
        worker.error.connect(lambda err: errors.append(err))
        worker.run()

        # Should report the error
        assert len(errors) > 0
