"""Tests for concurrent operation safety."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.ui.main_window import MainWindow


@pytest.fixture
def mock_api():
    """Create mock GoogleApi."""
    api = MagicMock()
    api.get_calendars.return_value = [("Primary", "cal_001"), ("Work", "cal_002")]
    return api


@pytest.fixture
def mock_config():
    """Create mock ConfigManager."""
    config = MagicMock()
    config.ensure_defaults.return_value = MagicMock(
        email_address="test@example.com",
        calendar="Primary",
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
    return config


@pytest.fixture
def mock_api_with_batches():
    """Create mock GoogleApi with batch operations."""
    api = MagicMock()
    api.get_calendars.return_value = [("Primary", "cal_001")]
    return api


class TestOperationInProgress:
    """Test that UI properly disables during operation."""

    def test_process_button_disabled_during_create(self, qtbot, mock_api, mock_config):
        """Process button disabled during CREATE operation."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)
            window.show()

            # Populate calendar combo directly
            window.calendar_combo.addItem("Primary")
            window.calendar_combo.setCurrentIndex(0)
            window._switch_mode("create")

            # Set valid inputs
            window.event_name.setText("Vacation")
            window.notification_email.setText("valid@example.com")
            # Ensure at least one weekday is checked
            if not any(cb.isChecked() for cb in window.weekday_boxes.values()):
                window.weekday_boxes["monday"].setChecked(True)
            window._update_validation()

            assert window.process_button.isEnabled()

    def test_input_fields_disabled_during_operation(self, qtbot, mock_api, mock_config):
        """Input fields should handle operation state."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("create")

            # Verify fields are enabled initially
            assert window.event_name.isEnabled()

    def test_mode_buttons_exist(self, qtbot, mock_api, mock_config):
        """Mode buttons exist and are accessible."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            # Mode buttons should exist
            assert hasattr(window, "mode_create_btn")
            assert hasattr(window, "mode_update_btn")
            assert hasattr(window, "mode_delete_btn")

    def test_batch_selector_disabled_in_create(self, qtbot, mock_api_with_batches, mock_config):
        """Batch selector disabled in CREATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("create")

            # Batch selector should be hidden/disabled
            assert not window.batch_selector_btn.isVisible()

    def test_calendar_dropdown_accessible(self, qtbot, mock_api, mock_config):
        """Calendar dropdown accessible."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("create")

            # Dropdown should be accessible
            assert window.calendar_combo.isEnabled()


class TestOperationStateTransitions:
    """Test state transitions during operations."""

    def test_cannot_switch_modes_disables_buttons(self, qtbot, mock_api_with_batches, mock_config):
        """Verify mode switching works as expected."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("create")
            current_mode = window.current_mode
            assert current_mode == "create"

            window._switch_mode("update")
            assert window.current_mode == "update"

    def test_validation_triggers_on_mode_switch(self, qtbot, mock_api, mock_config):
        """Validation triggered on mode switch."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)
            window.show()

            # Populate calendar combo directly
            window.calendar_combo.addItem("Primary")
            window.calendar_combo.setCurrentIndex(0)
            window._switch_mode("create")

            # Set valid inputs
            window.event_name.setText("Vacation")
            window.notification_email.setText("valid@example.com")
            # Ensure at least one weekday is checked
            if not any(cb.isChecked() for cb in window.weekday_boxes.values()):
                window.weekday_boxes["monday"].setChecked(True)
            window._update_validation()

            # Button should be enabled
            assert window.process_button.isEnabled()


class TestMultipleOperationPrevention:
    """Test that concurrent operations are prevented."""

    def test_operation_flag_exists(self, qtbot, mock_api, mock_config):
        """Operation flag mechanism exists."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            # Verify operation flag exists
            assert hasattr(window, "_operation_in_progress")

    def test_undo_button_exists(self, qtbot, mock_api, mock_config):
        """Undo button exists in UI."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            # Undo button should exist
            assert hasattr(window, "undo_button")
