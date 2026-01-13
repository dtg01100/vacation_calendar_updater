"""Tests for comprehensive validation of CREATE, UPDATE, and DELETE modes."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtWidgets

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


class TestCreateModeValidation:
    """Test input validation in CREATE mode."""

    def test_create_mode_event_name_required(self, qtbot, mock_api, mock_config):
        """Event name cannot be empty in CREATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("create")

            # Clear event name
            window.event_name.setText("")

            # Trigger validation
            window._update_validation()

            # Process button should be disabled
            assert not window.process_button.isEnabled()

    def test_create_mode_invalid_email_rejected(self, qtbot, mock_api, mock_config):
        """Invalid email address disables process button."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("create")

            # Set invalid email
            window.notification_email.setText("not-an-email")

            # Trigger validation
            window._update_validation()

            # Process button should be disabled
            assert not window.process_button.isEnabled()

    def test_create_mode_valid_email_accepted(self, qtbot, mock_api, mock_config):
        """Valid email allows button to be enabled (if other fields valid)."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)
            window.show()

            # Populate calendar combo directly
            window.calendar_combo.addItem("Primary")
            window.calendar_combo.setCurrentIndex(0)
            window._switch_mode("create")

            # Ensure all valid (dates are already set by default)
            window.event_name.setText("Vacation")
            window.notification_email.setText("valid@example.com")
            # Ensure at least one weekday is checked (should be by default)
            if not any(cb.isChecked() for cb in window.weekday_boxes.values()):
                window.weekday_boxes["monday"].setChecked(True)

            # Trigger validation
            window._update_validation()

            # Process button should be enabled
            assert window.process_button.isEnabled()

    def test_create_mode_weekday_required(self, qtbot, mock_api, mock_config):
        """At least one weekday must be selected."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("create")

            # Set all valid except uncheck all weekdays
            window.event_name.setText("Vacation")
            window.notification_email.setText("valid@example.com")
            window.calendar_combo.setCurrentIndex(0)

            # Uncheck all weekdays
            for checkbox in window.weekday_boxes.values():
                checkbox.setChecked(False)

            # Trigger validation
            window._update_validation()

            # Process button should be disabled
            assert not window.process_button.isEnabled()

    def test_create_mode_calendar_required(self, qtbot, mock_api, mock_config):
        """Calendar must be selected."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("create")

            # Set valid but don't select calendar
            window.event_name.setText("Vacation")
            window.notification_email.setText("valid@example.com")
            window.calendar_combo.setCurrentIndex(-1)  # No selection

            # Trigger validation
            window._update_validation()

            # Process button should be disabled
            assert not window.process_button.isEnabled()

    def test_create_mode_process_button_enabled_with_valid_inputs(self, qtbot, mock_api, mock_config):
        """Process button enabled when all required fields valid."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            qtbot.addWidget(window)
            window.show()

            # Populate calendar combo directly
            window.calendar_combo.addItem("Primary")
            window.calendar_combo.setCurrentIndex(0)
            window._switch_mode("create")

            # Set all valid
            window.event_name.setText("Vacation")
            window.notification_email.setText("valid@example.com")
            # Ensure at least one weekday is checked
            if not any(cb.isChecked() for cb in window.weekday_boxes.values()):
                window.weekday_boxes["monday"].setChecked(True)
            # Trigger validation
            window._update_validation()

            # Process button should be enabled
            assert window.process_button.isEnabled()


class TestUpdateModeValidation:
    """Test input validation in UPDATE mode."""

    def test_update_mode_batch_selection_required(self, qtbot, mock_api_with_batches, mock_config):
        """Batch must be selected in UPDATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")

            # Load batches
            window._on_batches_loaded(
                [
                    MagicMock(
                        batch_id="batch_001",
                        description="Test batch",
                        is_undone=False,
                    )
                ]
            )

            # Don't select batch - combo shows "Select..." by default
            window.batch_selector_combo.setCurrentIndex(-1)

            # Trigger validation
            window._update_validation()

            # Process button should be disabled
            assert not window.process_button.isEnabled()

    def test_update_mode_batch_selection_enables_button(self, qtbot, mock_api_with_batches, mock_config):
        """Selecting batch enables process button (if schedule valid)."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            qtbot.addWidget(window)
            window.show()

            # Populate calendar combo directly
            window.calendar_combo.addItem("Primary")
            window.calendar_combo.setCurrentIndex(0)
            window._switch_mode("update")

            # Set all schedule fields valid
            window.event_name.setText("Vacation")
            window.notification_email.setText("valid@example.com")
            # Ensure at least one weekday is checked
            if not any(cb.isChecked() for cb in window.weekday_boxes.values()):
                window.weekday_boxes["monday"].setChecked(True)

            # Load batches
            window._on_batches_loaded(
                [
                    MagicMock(
                        batch_id="batch_001",
                        description="Test batch",
                        is_undone=False,
                    )
                ]
            )

            # Select batch
            window.batch_selector_combo.setCurrentIndex(0)

            # Trigger validation
            window._update_validation()

            # Process button should be enabled
            assert window.process_button.isEnabled()

    def test_update_mode_inherits_create_validation(self, qtbot, mock_api_with_batches, mock_config):
        """UPDATE mode enforces all CREATE mode validation rules too."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")

            # Load batches
            window._on_batches_loaded(
                [
                    MagicMock(
                        batch_id="batch_001",
                        description="Test batch",
                        is_undone=False,
                    )
                ]
            )

            # Select batch but invalid email
            window.batch_selector_combo.setCurrentIndex(0)
            window.notification_email.setText("invalid-email")

            # Trigger validation
            window._update_validation()

            # Process button should be disabled (email invalid)
            assert not window.process_button.isEnabled()


class TestDeleteModeValidation:
    """Test input validation in DELETE mode."""

    def test_delete_mode_batch_selection_required(self, qtbot, mock_api_with_batches, mock_config):
        """Batch must be selected in DELETE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("delete")

            # Load batches
            window._on_batches_loaded(
                [
                    MagicMock(
                        batch_id="batch_001",
                        description="Test batch",
                        is_undone=False,
                    )
                ]
            )

            # Don't select batch
            window.batch_selector_combo.setCurrentIndex(-1)

            # Trigger validation
            window._update_validation()

            # Process button should be disabled
            assert not window.process_button.isEnabled()

    def test_delete_mode_batch_selection_enables_button(self, qtbot, mock_api_with_batches, mock_config):
        """Selecting batch enables process button in DELETE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("delete")

            # Load batches
            window._on_batches_loaded(
                [
                    MagicMock(
                        batch_id="batch_001",
                        description="Test batch",
                        is_undone=False,
                    )
                ]
            )

            # Select batch
            window.batch_selector_combo.setCurrentIndex(0)

            # Trigger validation
            window._update_validation()

            # Process button should be enabled
            assert window.process_button.isEnabled()

    def test_delete_mode_ignores_schedule_fields(self, qtbot, mock_api_with_batches, mock_config):
        """DELETE mode only requires batch selection, not schedule fields."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("delete")

            # Load batches
            window._on_batches_loaded(
                [
                    MagicMock(
                        batch_id="batch_001",
                        description="Test batch",
                        is_undone=False,
                    )
                ]
            )

            # Select batch but leave other fields empty/invalid
            window.batch_selector_combo.setCurrentIndex(0)
            window.event_name.setText("")
            window.notification_email.setText("invalid")

            # Trigger validation
            window._update_validation()

            # Process button should still be enabled (batch is all that matters)
            assert window.process_button.isEnabled()


class TestModeProcessButton:
    """Test process button state transitions across modes."""

    def test_process_button_label_changes_per_mode(self, qtbot, mock_api, mock_config):
        """Process button text changes based on mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            # CREATE mode
            window._switch_mode("create")
            assert "Insert" in window.process_button.text()

            # UPDATE mode
            window._switch_mode("update")
            assert "Update" in window.process_button.text()

            # DELETE mode
            window._switch_mode("delete")
            assert "Delete" in window.process_button.text()
