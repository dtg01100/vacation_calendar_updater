"""Tests for UndoWorker and RedoWorker.

Tests focus on critical paths: deletion/recreation of events, signal emissions,
404/410 error handling, email notifications, and progress reporting.
"""

import datetime as dt
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from app.services import CreatedEvent, EnhancedCreatedEvent
from app.workers import RedoWorker, UndoWorker


@pytest.fixture
def mock_api():
    """Create a mock GoogleApi."""
    api = MagicMock()
    api.delete_event = MagicMock()
    api.create_event = MagicMock()
    api.send_email = MagicMock()
    return api


@pytest.fixture
def sample_enhanced_events():
    """Create sample enhanced events for testing."""
    return [
        EnhancedCreatedEvent(
            event_id=f"event_{i}",
            calendar_id="cal_123",
            event_name="Test Event",
            start_time=dt.datetime(2024, 3, i + 1, 9, 0),
            end_time=dt.datetime(2024, 3, i + 1, 17, 0),
            created_at=dt.datetime.now(),
            batch_id="batch_123",
            request_snapshot={},
        )
        for i in range(3)
    ]


class TestUndoWorkerInit:
    """Test UndoWorker initialization."""

    def test_initialization(self, mock_api, sample_enhanced_events):
        """Test worker initializes with correct attributes."""
        worker = UndoWorker(
            mock_api,
            sample_enhanced_events,
            send_email=True,
            notification_email="test@example.com",
            batch_description="Test Batch",
        )

        assert worker.api == mock_api
        assert worker.events == sample_enhanced_events
        assert worker.send_email is True
        assert worker.notification_email == "test@example.com"
        assert worker.batch_description == "Test Batch"

    def test_has_required_signals(self, mock_api, sample_enhanced_events):
        """Test worker has finished, progress, and error signals."""
        worker = UndoWorker(
            mock_api,
            sample_enhanced_events,
            send_email=False,
            notification_email="test@example.com",
        )

        assert hasattr(worker, "finished")
        assert hasattr(worker, "progress")
        assert hasattr(worker, "error")

    def test_accepts_iterable_events(self, mock_api, sample_enhanced_events):
        """Test worker accepts any iterable of events."""
        # Test with list
        worker1 = UndoWorker(
            mock_api,
            sample_enhanced_events,
            send_email=False,
            notification_email="test@example.com",
        )
        assert len(worker1.events) == 3

        # Test with tuple
        worker2 = UndoWorker(
            mock_api,
            tuple(sample_enhanced_events),
            send_email=False,
            notification_email="test@example.com",
        )
        assert len(worker2.events) == 3


class TestUndoWorkerExecution:
    """Test undo worker execution."""

    def test_deletes_all_events(self, mock_api, sample_enhanced_events):
        """Test worker deletes all provided events."""
        mock_api.delete_event.return_value = None

        worker = UndoWorker(
            mock_api,
            sample_enhanced_events,
            send_email=False,
            notification_email="test@example.com",
        )

        deleted_ids = []
        worker.finished.connect(lambda ids: deleted_ids.extend(ids))

        worker.run()

        assert mock_api.delete_event.call_count == 3
        assert len(deleted_ids) == 3
        assert all(id in deleted_ids for id in ["event_0", "event_1", "event_2"])

    def test_calls_api_with_correct_params(self, mock_api, sample_enhanced_events):
        """Test API is called with correct parameters."""
        mock_api.delete_event.return_value = None

        worker = UndoWorker(
            mock_api,
            sample_enhanced_events,
            send_email=False,
            notification_email="test@example.com",
        )

        worker.run()

        # Check that delete_event was called with CreatedEvent objects
        for call in mock_api.delete_event.call_args_list:
            event = call[0][0]
            assert hasattr(event, "event_id")
            assert hasattr(event, "calendar_id")

    def test_emits_progress_for_each_deletion(self, mock_api, sample_enhanced_events):
        """Test progress signal emitted for each deleted event."""
        mock_api.delete_event.return_value = None

        worker = UndoWorker(
            mock_api,
            sample_enhanced_events,
            send_email=False,
            notification_email="test@example.com",
            batch_description="Test Batch",
        )

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))

        worker.run()

        deletion_messages = [msg for msg in progress_messages if "Deleted" in msg]
        assert len(deletion_messages) == 3
        assert all("event_" in msg for msg in deletion_messages)


class TestUndoWorker404Handling:
    """Test handling of 404/410 errors for already-deleted events."""

    def test_handles_404_gracefully(self, mock_api, sample_enhanced_events):
        """Test worker handles 404 errors without failing."""
        # Create mock 404 response
        mock_response = MagicMock()
        mock_response.status = 404
        mock_api.delete_event.side_effect = HttpError(
            resp=mock_response,
            content=b"Not Found"
        )

        worker = UndoWorker(
            mock_api,
            sample_enhanced_events,
            send_email=False,
            notification_email="test@example.com",
        )

        deleted_ids = []
        worker.finished.connect(lambda ids: deleted_ids.extend(ids))

        error_messages = []
        worker.error.connect(lambda msg: error_messages.append(msg))

        worker.run()

        # Should still report as "deleted" (gone from calendar)
        assert len(deleted_ids) == 3
        # Should not emit error
        assert len(error_messages) == 0

    def test_handles_410_gracefully(self, mock_api, sample_enhanced_events):
        """Test worker handles 410 (Gone) errors without failing."""
        mock_response = MagicMock()
        mock_response.status = 410
        mock_api.delete_event.side_effect = HttpError(
            resp=mock_response,
            content=b"Gone"
        )

        worker = UndoWorker(
            mock_api,
            sample_enhanced_events,
            send_email=False,
            notification_email="test@example.com",
        )

        deleted_ids = []
        worker.finished.connect(lambda ids: deleted_ids.extend(ids))

        worker.run()

        assert len(deleted_ids) == 3

    def test_emits_skip_message_for_404(self, mock_api, sample_enhanced_events):
        """Test progress message indicates skipped events."""
        mock_response = MagicMock()
        mock_response.status = 404
        mock_api.delete_event.side_effect = HttpError(
            resp=mock_response,
            content=b"Not Found"
        )

        worker = UndoWorker(
            mock_api,
            sample_enhanced_events,
            send_email=False,
            notification_email="test@example.com",
        )

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))

        worker.run()

        skip_messages = [msg for msg in progress_messages if "Skipped" in msg]
        assert len(skip_messages) == 3
        assert all("already deleted" in msg or "not found" in msg for msg in skip_messages)

    def test_reraises_other_http_errors(self, mock_api, sample_enhanced_events):
        """Test that non-404/410 HTTP errors are raised."""
        mock_response = MagicMock()
        mock_response.status = 500
        mock_api.delete_event.side_effect = HttpError(
            resp=mock_response,
            content=b"Internal Server Error"
        )

        worker = UndoWorker(
            mock_api,
            sample_enhanced_events,
            send_email=False,
            notification_email="test@example.com",
        )

        error_messages = []
        worker.error.connect(lambda msg: error_messages.append(msg))

        worker.run()

        assert len(error_messages) == 1
        assert "500" in error_messages[0] or "Internal Server Error" in error_messages[0]


class TestUndoWorkerEmailNotification:
    """Test email notification functionality."""

    def test_sends_email_when_enabled(self, mock_api, sample_enhanced_events):
        """Test email sent when send_email is True."""
        mock_api.delete_event.return_value = None

        worker = UndoWorker(
            mock_api,
            sample_enhanced_events,
            send_email=True,
            notification_email="test@example.com",
            batch_description="My Batch",
        )

        worker.run()

        mock_api.send_email.assert_called_once()
        call_args = mock_api.send_email.call_args
        assert call_args[0][0] == "test@example.com"
        assert "deleted" in call_args[0][1].lower()  # subject
        assert call_args[1]["enabled"] is True

    def test_no_email_when_disabled(self, mock_api, sample_enhanced_events):
        """Test email not sent when send_email is False."""
        mock_api.delete_event.return_value = None

        worker = UndoWorker(
            mock_api,
            sample_enhanced_events,
            send_email=False,
            notification_email="test@example.com",
        )

        worker.run()

        call_args = mock_api.send_email.call_args
        assert call_args[1]["enabled"] is False

    def test_email_contains_event_count(self, mock_api, sample_enhanced_events):
        """Test email contains number of deleted events."""
        mock_api.delete_event.return_value = None

        worker = UndoWorker(
            mock_api,
            sample_enhanced_events,
            send_email=True,
            notification_email="test@example.com",
            batch_description="Test Batch",
        )

        worker.run()

        email_body = mock_api.send_email.call_args[0][2]
        assert "3" in email_body  # 3 events deleted
        assert "Test Batch" in email_body

    def test_email_mentions_skipped_events(self, mock_api, sample_enhanced_events):
        """Test email mentions skipped events when some were 404."""
        # Make 2 succeed, 1 fail with 404
        mock_response_404 = MagicMock()
        mock_response_404.status = 404

        call_count = [0]
        def delete_with_404(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise HttpError(resp=mock_response_404, content=b"Not Found")
            return None

        mock_api.delete_event.side_effect = delete_with_404

        worker = UndoWorker(
            mock_api,
            sample_enhanced_events,
            send_email=True,
            notification_email="test@example.com",
        )

        worker.run()

        email_body = mock_api.send_email.call_args[0][2]
        assert "were skipped" in email_body


class TestRedoWorkerInit:
    """Test RedoWorker initialization."""

    def test_initialization(self, mock_api, sample_enhanced_events):
        """Test worker initializes with correct attributes."""
        worker = RedoWorker(
            mock_api,
            sample_enhanced_events,
            batch_description="Test Batch",
        )

        assert worker.api == mock_api
        assert worker.events == sample_enhanced_events
        assert worker.batch_description == "Test Batch"

    def test_has_required_signals(self, mock_api, sample_enhanced_events):
        """Test worker has finished, progress, and error signals."""
        worker = RedoWorker(
            mock_api,
            sample_enhanced_events,
            batch_description="Test",
        )

        assert hasattr(worker, "finished")
        assert hasattr(worker, "progress")
        assert hasattr(worker, "error")


class TestRedoWorkerExecution:
    """Test redo worker execution."""

    def test_recreates_all_events(self, mock_api, sample_enhanced_events):
        """Test worker recreates all provided events."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event_123",
            calendar_id="cal_123"
        )

        worker = RedoWorker(
            mock_api,
            sample_enhanced_events,
            batch_description="Test Batch",
        )

        recreated_ids = []
        worker.finished.connect(lambda ids: recreated_ids.extend(ids))

        worker.run()

        assert mock_api.create_event.call_count == 3
        assert len(recreated_ids) == 3

    def test_calls_api_with_correct_params(self, mock_api, sample_enhanced_events):
        """Test API called with correct event parameters."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event_123",
            calendar_id="cal_123"
        )

        worker = RedoWorker(
            mock_api,
            sample_enhanced_events,
            batch_description="Test",
        )

        worker.run()

        # Check first call
        first_call = mock_api.create_event.call_args_list[0]
        assert first_call[0][0] == "cal_123"  # calendar_id
        assert first_call[0][1] == "Test Event"  # event_name
        assert isinstance(first_call[0][2], dt.datetime)  # start_time
        assert isinstance(first_call[0][3], dt.datetime)  # end_time

    def test_preserves_event_times(self, mock_api, sample_enhanced_events):
        """Test recreated events have same times as originals."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_123"
        )

        worker = RedoWorker(
            mock_api,
            sample_enhanced_events,
            batch_description="Test",
        )

        worker.run()

        # Check that create_event was called with original times
        for i, call in enumerate(mock_api.create_event.call_args_list):
            start_time = call[0][2]
            end_time = call[0][3]
            assert start_time == sample_enhanced_events[i].start_time
            assert end_time == sample_enhanced_events[i].end_time

    def test_emits_progress_for_each_recreation(self, mock_api, sample_enhanced_events):
        """Test progress signal emitted for each recreated event."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_123"
        )

        worker = RedoWorker(
            mock_api,
            sample_enhanced_events,
            batch_description="Test",
        )

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))

        worker.run()

        recreation_messages = [msg for msg in progress_messages if "Recreated" in msg]
        assert len(recreation_messages) == 3


class TestRedoWorker404Handling:
    """Test handling of errors during redo."""

    def test_handles_404_calendar_not_found(self, mock_api, sample_enhanced_events):
        """Test worker handles 404 when calendar doesn't exist."""
        mock_response = MagicMock()
        mock_response.status = 404
        mock_api.create_event.side_effect = HttpError(
            resp=mock_response,
            content=b"Calendar Not Found"
        )

        worker = RedoWorker(
            mock_api,
            sample_enhanced_events,
            batch_description="Test",
        )

        recreated_ids = []
        worker.finished.connect(lambda ids: recreated_ids.extend(ids))

        error_messages = []
        worker.error.connect(lambda msg: error_messages.append(msg))

        worker.run()

        # Should complete without error signal
        assert len(error_messages) == 0
        # No events recreated
        assert len(recreated_ids) == 0

    def test_emits_skip_message_for_404(self, mock_api, sample_enhanced_events):
        """Test progress message for skipped events."""
        mock_response = MagicMock()
        mock_response.status = 404
        mock_api.create_event.side_effect = HttpError(
            resp=mock_response,
            content=b"Not Found"
        )

        worker = RedoWorker(
            mock_api,
            sample_enhanced_events,
            batch_description="Test",
        )

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))

        worker.run()

        skip_messages = [msg for msg in progress_messages if "Skipped" in msg]
        assert len(skip_messages) == 3
        assert all("calendar not found" in msg for msg in skip_messages)

    def test_reraises_other_http_errors(self, mock_api, sample_enhanced_events):
        """Test non-404/410 errors are raised."""
        mock_response = MagicMock()
        mock_response.status = 403
        mock_api.create_event.side_effect = HttpError(
            resp=mock_response,
            content=b"Forbidden"
        )

        worker = RedoWorker(
            mock_api,
            sample_enhanced_events,
            batch_description="Test",
        )

        error_messages = []
        worker.error.connect(lambda msg: error_messages.append(msg))

        worker.run()

        assert len(error_messages) == 1


class TestRedoWorkerProgress:
    """Test progress reporting functionality."""

    def test_completion_message(self, mock_api, sample_enhanced_events):
        """Test completion progress message."""
        mock_api.create_event.return_value = CreatedEvent(
            event_id="new_event",
            calendar_id="cal_123"
        )

        worker = RedoWorker(
            mock_api,
            sample_enhanced_events,
            batch_description="Test",
        )

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))

        worker.run()

        completion_messages = [msg for msg in progress_messages if "complete" in msg]
        assert len(completion_messages) >= 1
        assert "3" in completion_messages[0]  # 3 events recreated

    def test_mixed_success_and_skip(self, mock_api, sample_enhanced_events):
        """Test progress when some events recreated, some skipped."""
        mock_response = MagicMock()
        mock_response.status = 404

        call_count = [0]
        def create_with_some_404(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise HttpError(resp=mock_response, content=b"Not Found")
            return CreatedEvent(event_id="new_event", calendar_id="cal_123")

        mock_api.create_event.side_effect = create_with_some_404

        worker = RedoWorker(
            mock_api,
            sample_enhanced_events,
            batch_description="Test",
        )

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))

        recreated_ids = []
        worker.finished.connect(lambda ids: recreated_ids.extend(ids))

        worker.run()

        # Should have 2 recreated, 1 skipped
        assert len(recreated_ids) == 2
        skip_messages = [msg for msg in progress_messages if "could not be recreated" in msg]
        assert len(skip_messages) >= 1


class TestWorkerEdgeCases:
    """Test edge cases for both workers."""

    def test_undo_with_empty_event_list(self, mock_api):
        """Test UndoWorker with empty event list."""
        worker = UndoWorker(
            mock_api,
            [],
            send_email=False,
            notification_email="test@example.com",
        )

        deleted_ids = []
        worker.finished.connect(lambda ids: deleted_ids.extend(ids))

        worker.run()

        assert len(deleted_ids) == 0
        assert mock_api.delete_event.call_count == 0

    def test_redo_with_empty_event_list(self, mock_api):
        """Test RedoWorker with empty event list."""
        worker = RedoWorker(
            mock_api,
            [],
            batch_description="Empty",
        )

        recreated_ids = []
        worker.finished.connect(lambda ids: recreated_ids.extend(ids))

        worker.run()

        assert len(recreated_ids) == 0
        assert mock_api.create_event.call_count == 0

    def test_undo_with_single_event(self, mock_api, sample_enhanced_events):
        """Test UndoWorker with single event."""
        mock_api.delete_event.return_value = None

        worker = UndoWorker(
            mock_api,
            [sample_enhanced_events[0]],
            send_email=False,
            notification_email="test@example.com",
        )

        deleted_ids = []
        worker.finished.connect(lambda ids: deleted_ids.extend(ids))

        worker.run()

        assert len(deleted_ids) == 1
        assert mock_api.delete_event.call_count == 1
