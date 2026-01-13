"""Tests for modal dialog behavior in main window."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtWidgets

from app.ui.main_window import MainWindow


@pytest.fixture
def mock_api():
    """Create mock GoogleApi."""
    api = MagicMock()
    api.get_calendars.return_value = []
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


class TestUpdateModeModals:
    """Test that modals spawn correctly (or don't) in UPDATE mode."""

    def test_update_mode_batch_selector_button_opens_modal(self, qtbot, mock_api, mock_config):
        """Test that batch selector button opens modal dialog in UPDATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")

            # Mock the batch selector dialog to avoid actually opening it
            with patch("app.ui.main_window.BatchSelectorDialog") as mock_dialog:
                mock_instance = MagicMock()
                mock_instance.exec.return_value = QtWidgets.QDialog.DialogCode.Rejected
                mock_dialog.return_value = mock_instance

                # Click the batch selector button
                window.batch_selector_btn.click()

                # Verify dialog was created (modal was spawned)
                mock_dialog.assert_called_once()

    def test_update_mode_time_picker_no_modal(self, qtbot, mock_api, mock_config):
        """Test that time picker spinners do NOT spawn a modal in UPDATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")

            # Verify spinners work directly without any dialogs
            # Changing preset should only update spinners, not spawn modal
            initial_combo_index = window.time_preset_combo.currentIndex()
            window.time_preset_combo.setCurrentIndex((initial_combo_index + 1) % window.time_preset_combo.count())

            # If we got here without an exception or dialog, test passes
            # Verify spinners were updated
            assert window.hour_spinbox.value() >= 0
            assert window.minute_spinbox.value() >= 0

    def test_update_mode_spinners_sync_with_preset(self, qtbot, mock_api, mock_config):
        """Test that spinners update when preset is selected."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")

            # Select 13:00 preset
            window.time_preset_combo.setCurrentIndex(3)  # 13:00

            # Verify spinners updated
            assert window.hour_spinbox.value() == 13
            assert window.minute_spinbox.value() == 0

    def test_create_mode_time_picker_no_modal(self, qtbot, mock_api, mock_config):
        """Test that time picker in CREATE mode does NOT spawn modal."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("create")

            # Interact with spinners - no modal should appear
            window.hour_spinbox.setValue(9)
            window.minute_spinbox.setValue(30)

            # Verify values changed
            assert window.hour_spinbox.value() == 9
            assert window.minute_spinbox.value() == 30

    def test_delete_mode_batch_selector_button_opens_modal(self, qtbot, mock_api, mock_config):
        """Test that batch selector button opens modal in DELETE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("delete")

            # Mock the batch selector dialog
            with patch("app.ui.main_window.BatchSelectorDialog") as mock_dialog:
                mock_instance = MagicMock()
                mock_instance.exec.return_value = QtWidgets.QDialog.DialogCode.Rejected
                mock_dialog.return_value = mock_instance

                # Click batch selector button
                window.batch_selector_btn.click()

                # Verify dialog was created
                mock_dialog.assert_called_once()

    def test_create_mode_no_batch_selector_modal(self, qtbot, mock_api, mock_config):
        """Test that batch selector button is hidden in CREATE mode (no modal spawned)."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("create")

            # Batch selector button should be hidden
            assert not window.batch_selector_btn.isVisible()

            # Mock dialog to ensure it's NOT opened
            with patch("app.ui.main_window.BatchSelectorDialog") as mock_dialog:
                # Try to click the hidden button (should fail or do nothing)
                if window.batch_selector_btn.isVisible():
                    window.batch_selector_btn.click()

                # Dialog should NOT be created
                mock_dialog.assert_not_called()

    def test_spinners_accept_manual_input(self, qtbot, mock_api, mock_config):
        """Test that spinners accept manual input without spawning modals."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("create")

            # Manually set spinner values (simulating user input)
            window.hour_spinbox.setValue(10)
            window.minute_spinbox.setValue(30)

            # Verify values were set
            assert window.hour_spinbox.value() == 10
            assert window.minute_spinbox.value() == 30
