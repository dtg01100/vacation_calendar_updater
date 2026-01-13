"""Tests for worker classes: DeleteWorker and UpdateWorker."""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from app.services import EnhancedCreatedEvent
from app.validation import ScheduleRequest
from app.workers import DeleteWorker, UpdateWorker


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
            start_time=dt.datetime(2024, 1, 15 + i, 9, 0),
            end_time=dt.datetime(2024, 1, 15 + i, 10, 0),
            created_at=dt.datetime.now(),
            batch_id="batch_1",
            request_snapshot={},
        )
        for i in range(3)
    ]


class TestDeleteWorker:
    """Tests for DeleteWorker."""

    def test_delete_worker_initialization(self, mock_api, sample_enhanced_events):
        """Test DeleteWorker initializes with correct attributes."""
        worker = DeleteWorker(
            mock_api,
            sample_enhanced_events,
            send_email=True,
            notification_email="test@example.com",
            batch_description="Test batch",
        )

        assert worker.api == mock_api
        assert worker.events == sample_enhanced_events
        assert worker.send_email is True
        assert worker.notification_email == "test@example.com"
        assert worker.batch_description == "Test batch"

    def test_delete_worker_has_required_signals(self, mock_api, sample_enhanced_events):
        """Test DeleteWorker has finished, progress, and error signals."""
        worker = DeleteWorker(
            mock_api,
            sample_enhanced_events,
            send_email=False,
            notification_email="test@example.com",
        )

        assert hasattr(worker, "finished")
        assert hasattr(worker, "progress")
        assert hasattr(worker, "error")

    def test_delete_worker_emits_progress_signals(self, mock_api, sample_enhanced_events):
        """Test DeleteWorker emits progress during deletion."""
        worker = DeleteWorker(
            mock_api,
            sample_enhanced_events,
            send_email=False,
            notification_email="test@example.com",
            batch_description="Test batch",
        )

        mock_api.delete_event.return_value = None
        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))

        worker.run()

        assert len(progress_messages) > 0
        assert any("Deleted" in msg for msg in progress_messages)

    def test_delete_worker_handles_404_errors(self, mock_api, sample_enhanced_events):
        """Test DeleteWorker handles 404 errors gracefully."""
        worker = DeleteWorker(
            mock_api,
            sample_enhanced_events,
            send_email=False,
            notification_email="test@example.com",
            batch_description="Test batch",
        )

        error_response = MagicMock()
        error_response.status = 404
        mock_api.delete_event.side_effect = HttpError(error_response, b"Not found")

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))

        worker.run()

        assert any("Skipped" in msg for msg in progress_messages)

    def test_delete_worker_emits_finished_with_correct_data(
        self, mock_api, sample_enhanced_events
    ):
        """Test DeleteWorker emits finished signal with event IDs and batch description."""
        worker = DeleteWorker(
            mock_api,
            sample_enhanced_events,
            send_email=False,
            notification_email="test@example.com",
            batch_description="Test batch",
        )

        mock_api.delete_event.return_value = None
        finished_data = []
        worker.finished.connect(lambda ids, desc: finished_data.append((ids, desc)))

        worker.run()

        assert len(finished_data) == 1
        deleted_ids, batch_desc = finished_data[0]
        assert len(deleted_ids) == len(sample_enhanced_events)
        assert batch_desc == "Test batch"

    def test_delete_worker_sends_email_when_enabled(
        self, mock_api, sample_enhanced_events
    ):
        """Test DeleteWorker sends email notification when enabled."""
        worker = DeleteWorker(
            mock_api,
            sample_enhanced_events,
            send_email=True,
            notification_email="user@example.com",
            batch_description="Test batch",
        )

        mock_api.delete_event.return_value = None
        worker.run()

        assert mock_api.send_email.called

    def test_delete_worker_skips_410_errors(self, mock_api, sample_enhanced_events):
        """Test DeleteWorker handles 410 Gone errors gracefully."""
        worker = DeleteWorker(
            mock_api,
            sample_enhanced_events,
            send_email=False,
            notification_email="test@example.com",
            batch_description="Test batch",
        )

        error_response = MagicMock()
        error_response.status = 410
        mock_api.delete_event.side_effect = HttpError(error_response, b"Gone")

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))

        worker.run()

        # Should still process all events
        assert any("Skipped" in msg or "Deleted" in msg for msg in progress_messages)


class TestUpdateWorker:
    """Tests for UpdateWorker."""

    @pytest.fixture
    def sample_request(self):
        """Create a sample ScheduleRequest."""
        return ScheduleRequest(
            event_name="Updated Event",
            notification_email="test@example.com",
            calendar_name="Primary",
            start_date=dt.date(2024, 2, 15),
            end_date=dt.date(2024, 2, 20),
            start_time=dt.time(10, 0),
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

    def test_update_worker_initialization(
        self, mock_api, sample_enhanced_events, sample_request
    ):
        """Test UpdateWorker initializes with correct attributes."""
        worker = UpdateWorker(
            mock_api,
            "cal_123",
            sample_enhanced_events,
            sample_request,
            send_email=True,
            notification_email="test@example.com",
        )

        assert worker.api == mock_api
        assert worker.calendar_id == "cal_123"
        assert worker.old_events == sample_enhanced_events
        assert worker.new_request == sample_request

    def test_update_worker_has_required_signals(
        self, mock_api, sample_enhanced_events, sample_request
    ):
        """Test UpdateWorker has finished, progress, and error signals."""
        worker = UpdateWorker(
            mock_api,
            "cal_123",
            sample_enhanced_events,
            sample_request,
            send_email=False,
            notification_email="test@example.com",
        )

        assert hasattr(worker, "finished")
        assert hasattr(worker, "progress")
        assert hasattr(worker, "error")

    def test_update_worker_deletes_old_events(
        self, mock_api, sample_enhanced_events, sample_request
    ):
        """Test UpdateWorker deletes old events before creating new ones."""
        worker = UpdateWorker(
            mock_api,
            "cal_123",
            sample_enhanced_events,
            sample_request,
            send_email=False,
            notification_email="test@example.com",
        )

        mock_api.delete_event.return_value = None
        mock_api.create_event.return_value = MagicMock(
            event_id="new_event", calendar_id="cal_123"
        )

        worker.run()

        assert mock_api.delete_event.call_count >= len(sample_enhanced_events)

    def test_update_worker_creates_new_events(
        self, mock_api, sample_enhanced_events, sample_request
    ):
        """Test UpdateWorker creates new events from the schedule request."""
        worker = UpdateWorker(
            mock_api,
            "cal_123",
            sample_enhanced_events,
            sample_request,
            send_email=False,
            notification_email="test@example.com",
        )

        mock_api.delete_event.return_value = None
        mock_api.create_event.return_value = MagicMock(
            event_id="new_event", calendar_id="cal_123"
        )

        finished_events = []
        worker.finished.connect(lambda events: finished_events.append(events))

        worker.run()

        assert len(finished_events) > 0
        assert len(finished_events[0]) > 0
        assert all(isinstance(e, EnhancedCreatedEvent) for e in finished_events[0])

    def test_update_worker_emits_progress_signals(
        self, mock_api, sample_enhanced_events, sample_request
    ):
        """Test UpdateWorker emits progress signals during execution."""
        worker = UpdateWorker(
            mock_api,
            "cal_123",
            sample_enhanced_events,
            sample_request,
            send_email=False,
            notification_email="test@example.com",
        )

        mock_api.delete_event.return_value = None
        mock_api.create_event.return_value = MagicMock(
            event_id="new_event", calendar_id="cal_123"
        )

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))

        worker.run()

        assert len(progress_messages) > 0
        assert any("Deleted" in msg for msg in progress_messages)
        assert any("Created" in msg for msg in progress_messages)

    def test_update_worker_sends_email(
        self, mock_api, sample_enhanced_events, sample_request
    ):
        """Test UpdateWorker sends notification email when enabled."""
        worker = UpdateWorker(
            mock_api,
            "cal_123",
            sample_enhanced_events,
            sample_request,
            send_email=True,
            notification_email="user@example.com",
        )

        mock_api.delete_event.return_value = None
        mock_api.create_event.return_value = MagicMock(
            event_id="new_event", calendar_id="cal_123"
        )

        worker.run()

        assert mock_api.send_email.called

    def test_update_worker_handles_already_deleted_events(
        self, mock_api, sample_enhanced_events, sample_request
    ):
        """Test UpdateWorker continues when old events are already deleted."""
        worker = UpdateWorker(
            mock_api,
            "cal_123",
            sample_enhanced_events,
            sample_request,
            send_email=False,
            notification_email="test@example.com",
        )

        error_response = MagicMock()
        error_response.status = 404
        mock_api.delete_event.side_effect = HttpError(error_response, b"Not found")
        mock_api.create_event.return_value = MagicMock(
            event_id="new_event", calendar_id="cal_123"
        )

        # Should not raise and should still create new events
        worker.run()

        assert mock_api.create_event.called

    def test_update_worker_batch_id_is_unique(
        self, mock_api, sample_enhanced_events, sample_request
    ):
        """Test that UpdateWorker generates unique batch ID for updated events."""
        worker1 = UpdateWorker(
            mock_api,
            "cal_123",
            sample_enhanced_events,
            sample_request,
            send_email=False,
            notification_email="test@example.com",
        )

        worker2 = UpdateWorker(
            mock_api,
            "cal_123",
            sample_enhanced_events,
            sample_request,
            send_email=False,
            notification_email="test@example.com",
        )

        assert worker1.batch_id != worker2.batch_id
