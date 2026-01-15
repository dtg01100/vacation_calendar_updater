"""Tests for StartupWorker.

Tests focus on background loading of user email and calendar list,
error handling, and signal emissions.
"""

from unittest.mock import MagicMock

import pytest

from app.workers import StartupWorker


@pytest.fixture
def mock_api():
    """Create a mock GoogleApi."""
    api = MagicMock()
    api.user_email = MagicMock(return_value="user@example.com")
    api.list_calendars = MagicMock(return_value=(
        ["Calendar 1", "Calendar 2"],
        [{"id": "cal1", "summary": "Calendar 1"}, {"id": "cal2", "summary": "Calendar 2"}]
    ))
    return api


class TestStartupWorkerInit:
    """Test StartupWorker initialization."""

    def test_initialization(self, mock_api):
        """Test worker initializes with correct attributes."""
        worker = StartupWorker(mock_api)

        assert worker.api == mock_api

    def test_has_required_signals(self, mock_api):
        """Test worker has finished and error signals."""
        worker = StartupWorker(mock_api)

        assert hasattr(worker, "finished")
        assert hasattr(worker, "error")

    def test_is_qthread(self, mock_api):
        """Test worker inherits from QThread."""
        worker = StartupWorker(mock_api)
        # StartupWorker inherits from QThread, not BaseWorker
        assert hasattr(worker, "start")  # QThread method


class TestStartupWorkerExecution:
    """Test startup worker execution."""

    def test_loads_user_email(self, mock_api):
        """Test worker loads user email."""
        worker = StartupWorker(mock_api)

        result = []
        worker.finished.connect(lambda data: result.append(data))

        worker.run()

        assert len(result) == 1
        user_email, calendar_data = result[0]
        assert user_email == "user@example.com"

    def test_loads_calendar_list(self, mock_api):
        """Test worker loads calendar list."""
        worker = StartupWorker(mock_api)

        result = []
        worker.finished.connect(lambda data: result.append(data))

        worker.run()

        assert len(result) == 1
        user_email, (calendar_names, calendar_items) = result[0]
        assert calendar_names == ["Calendar 1", "Calendar 2"]
        assert len(calendar_items) == 2
        assert calendar_items[0]["id"] == "cal1"

    def test_returns_tuple_format(self, mock_api):
        """Test worker returns correct tuple format."""
        worker = StartupWorker(mock_api)

        result = []
        worker.finished.connect(lambda data: result.append(data))

        worker.run()

        # Format should be (user_email, (calendar_names, calendar_items))
        user_email, calendar_data = result[0]
        calendar_names, calendar_items = calendar_data

        assert isinstance(user_email, str)
        assert isinstance(calendar_names, list)
        assert isinstance(calendar_items, list)


class TestStartupWorkerErrorHandling:
    """Test error handling during startup."""

    def test_emits_error_on_email_failure(self, mock_api):
        """Test error signal when user_email fails."""
        mock_api.user_email.side_effect = Exception("Email API Error")

        worker = StartupWorker(mock_api)

        error_messages = []
        worker.error.connect(lambda msg: error_messages.append(msg))

        worker.run()

        assert len(error_messages) == 1
        assert "Email API Error" in error_messages[0]

    def test_emits_error_on_calendar_list_failure(self, mock_api):
        """Test error signal when list_calendars fails."""
        mock_api.list_calendars.side_effect = Exception("Calendar API Error")

        worker = StartupWorker(mock_api)

        error_messages = []
        worker.error.connect(lambda msg: error_messages.append(msg))

        worker.run()

        assert len(error_messages) == 1
        assert "Calendar API Error" in error_messages[0]

    def test_no_finished_signal_on_error(self, mock_api):
        """Test finished signal not emitted when error occurs."""
        mock_api.user_email.side_effect = Exception("API Error")

        worker = StartupWorker(mock_api)

        finished_called = []
        worker.finished.connect(lambda data: finished_called.append(data))

        worker.run()

        assert len(finished_called) == 0


class TestStartupWorkerEdgeCases:
    """Test edge cases in startup worker."""

    def test_handles_empty_calendar_list(self, mock_api):
        """Test worker handles empty calendar list."""
        mock_api.list_calendars.return_value = ([], [])

        worker = StartupWorker(mock_api)

        result = []
        worker.finished.connect(lambda data: result.append(data))

        worker.run()

        user_email, (calendar_names, calendar_items) = result[0]
        assert calendar_names == []
        assert calendar_items == []

    def test_handles_long_calendar_list(self, mock_api):
        """Test worker handles many calendars."""
        many_calendars = [f"Calendar {i}" for i in range(100)]
        many_items = [{"id": f"cal{i}", "summary": f"Calendar {i}"} for i in range(100)]
        mock_api.list_calendars.return_value = (many_calendars, many_items)

        worker = StartupWorker(mock_api)

        result = []
        worker.finished.connect(lambda data: result.append(data))

        worker.run()

        user_email, (calendar_names, calendar_items) = result[0]
        assert len(calendar_names) == 100
        assert len(calendar_items) == 100

    def test_handles_special_characters_in_email(self, mock_api):
        """Test worker handles special characters in email."""
        mock_api.user_email.return_value = "user+test@example.co.uk"

        worker = StartupWorker(mock_api)

        result = []
        worker.finished.connect(lambda data: result.append(data))

        worker.run()

        user_email, _ = result[0]
        assert user_email == "user+test@example.co.uk"

    def test_handles_special_characters_in_calendar_names(self, mock_api):
        """Test worker handles special characters in calendar names."""
        special_names = ["Calendar 🗓️", "Test's Calendar", "Work & Personal"]
        special_items = [{"id": f"cal{i}", "summary": name} for i, name in enumerate(special_names)]
        mock_api.list_calendars.return_value = (special_names, special_items)

        worker = StartupWorker(mock_api)

        result = []
        worker.finished.connect(lambda data: result.append(data))

        worker.run()

        user_email, (calendar_names, calendar_items) = result[0]
        assert calendar_names == special_names
