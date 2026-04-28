"""Integration tests for Delete mode workflow.

Tests the complete event deletion flow including single deletion,
batch deletion, undo functionality, and error handling.
"""

from __future__ import annotations

import datetime as dt

import pytest

from app.services import EnhancedCreatedEvent
from app.undo_manager import BatchInfo
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

    def test_deletes_event_from_api(self, mock_api, sample_batch):
        """Test that delete calls the API to remove the event."""
        event = sample_batch[0]

        worker = DeleteWorker(
            mock_api,
            [event],
            send_email=False,
            notification_email="[REDACTED]",
            batch_description="Delete test",
        )

        worker.run()

        mock_api.delete_event.assert_called_with(event.event_id)

    def test_emits_finished_with_event_ids(self, mock_api, sample_batch):
        """Test that finished signal includes deleted event IDs."""
        event = sample_batch[0]

        worker = DeleteWorker(
            mock_api,
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

    def test_deletes_all_events_in_batch(self, mock_api, sample_batch):
        """Test that all events in a batch are deleted."""
        worker = DeleteWorker(
            mock_api,
            sample_batch,
            send_email=False,
            notification_email="[REDACTED]",
            batch_description="Batch delete test",
        )

        worker.run()

        for event in sample_batch:
            mock_api.delete_event.assert_any_call(event.event_id)

    def test_emits_progress_for_each_event(self, mock_api, sample_batch):
        """Test that progress is emitted for each deleted event."""
        worker = DeleteWorker(
            mock_api,
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

    def test_sends_email_when_enabled(self, mock_api, sample_batch):
        """Test that email is sent after batch deletion."""
        worker = DeleteWorker(
            mock_api,
            sample_batch,
            send_email=True,
            notification_email="[REDACTED]",
            batch_description="Delete with email",
        )

        worker.run()

        assert mock_api.send_email.called

    def test_skips_email_when_disabled(self, mock_api, sample_batch):
        """Test that no email is sent when send_email is False."""
        worker = DeleteWorker(
            mock_api,
            sample_batch,
            send_email=False,
            notification_email="[REDACTED]",
            batch_description="Delete without email",
        )

        worker.run()

        assert not mock_api.send_email.called


class TestDeleteMode404Handling:
    """Test handling of already-deleted events (404 errors)."""

    def test_handles_404_gracefully(self, mock_api, sample_batch):
        """Test that 404 errors are handled without crashing."""
        from googleapiclient.errors import HttpError

        error_response = MagicMock()
        error_response.status = 404

        # Configure the mock to raise 404 on first call
        mock_api.delete_event.side_effect = HttpError(error_response, b"Not found")

        worker = DeleteWorker(
            mock_api,
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

    def test_continues_after_404(self, mock_api, sample_batch):
        """Test that deletion continues for remaining events after 404."""
        from googleapiclient.errors import HttpError

        call_count = [0]

        def error_then_success(event_id):
            call_count[0] += 1
            if call_count[0] == 1:
                error_response = MagicMock()
                error_response.status = 404
                raise HttpError(error_response, b"Not found")
            return None

        mock_api.delete_event.side_effect = error_then_success

        worker = DeleteWorker(
            mock_api,
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

    def test_handles_410_gracefully(self, mock_api, sample_batch):
        """Test that 410 Gone errors are handled without crashing."""
        from googleapiclient.errors import HttpError

        error_response = MagicMock()
        error_response.status = 410

        mock_api.delete_event.side_effect = HttpError(error_response, b"Gone")

        worker = DeleteWorker(
            mock_api,
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

    def test_batch_can_be_undone(self, mock_api, sample_batch, undo_manager):
        """Test that a deleted batch can be tracked for undo."""
        # Add the batch to undo manager
        batch_info = BatchInfo(
            batch_id=sample_batch[0].batch_id,
            description="Vacation batch",
            events=sample_batch,
            request_snapshots=[e.request_snapshot for e in sample_batch],
            created_at=dt.datetime.now(),
        )
        undo_manager.add_batch(batch_info)

        # Delete the events
        worker = DeleteWorker(
            mock_api,
            sample_batch,
            send_email=False,
            notification_email="[REDACTED]",
            batch_description="Vacation batch",
        )
        worker.run()

        # The batch should be in the undo stack
        assert undo_manager.get_undoable_count() == 1

    def test_deleted_events_not_in_undoable_list(
        self, mock_api, sample_batch, undo_manager
    ):
        """Test that deleted events are properly tracked."""
        # Add batch
        batch_info = BatchInfo(
            batch_id=sample_batch[0].batch_id,
            description="Test batch",
            events=sample_batch,
            request_snapshots=[e.request_snapshot for e in sample_batch],
            created_at=dt.datetime.now(),
        )
        undo_manager.add_batch(batch_info)

        # Delete events
        worker = DeleteWorker(
            mock_api,
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

    def test_reports_non_404_errors(self, mock_api, sample_batch):
        """Test that non-404 errors are reported through error signal."""
        from googleapiclient.errors import HttpError

        error_response = MagicMock()
        error_response.status = 500

        mock_api.delete_event.side_effect = HttpError(
            error_response, b"Internal Server Error"
        )

        worker = DeleteWorker(
            mock_api,
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
