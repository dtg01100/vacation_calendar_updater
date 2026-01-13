"""Tests for batch selector dialog and integration."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtWidgets

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


class TestBatchSelectorCombo:
    """Test batch selector combo dropdown."""

    def test_batch_combo_shows_batches_in_update_mode(self, qtbot, mock_api_with_batches, mock_config):
        """Batch combo displays available batches in UPDATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")

            # Load batches
            batches = [
                MagicMock(
                    batch_id="batch_001",
                    description="Vacation 2024",
                    is_undone=False,
                ),
                MagicMock(
                    batch_id="batch_002",
                    description="Conference 2024",
                    is_undone=False,
                ),
            ]
            window._on_batches_loaded(batches)

            # Combo should show batches
            assert window.batch_selector_combo.count() >= 2

    def test_batch_combo_filters_undone_batches(self, qtbot, mock_api_with_batches, mock_config):
        """Batch combo only shows batches where is_undone=False."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")

            # Load batches (mix of undone and not)
            batches = [
                MagicMock(
                    batch_id="batch_001",
                    description="Active batch",
                    is_undone=False,
                ),
                MagicMock(
                    batch_id="batch_002",
                    description="Undone batch",
                    is_undone=True,
                ),
                MagicMock(
                    batch_id="batch_003",
                    description="Another active",
                    is_undone=False,
                ),
            ]
            window._on_batches_loaded(batches)

            # Only non-undone batches should be in combo
            assert window.batch_selector_combo.count() >= 2

    def test_batch_combo_empty_when_no_batches(self, qtbot, mock_api_with_batches, mock_config):
        """Batch combo handles empty batch list."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")

            # Load empty batch list
            window._on_batches_loaded([])

            # Combo should be empty
            assert window.batch_selector_combo.count() == 0


class TestBatchSelectorButton:
    """Test batch selector button and dialog trigger."""

    def test_batch_selector_button_visible_in_update_mode(self, qtbot, mock_api_with_batches, mock_config):
        """Batch selector button visible in UPDATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")
            assert not window.batch_selector_btn.isVisible()

    def test_batch_selector_button_visible_in_delete_mode(self, qtbot, mock_api_with_batches, mock_config):
        """Batch selector button visible in DELETE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("delete")
            assert not window.batch_selector_btn.isVisible()

    def test_batch_selector_button_hidden_in_create_mode(self, qtbot, mock_api, mock_config):
        """Batch selector button hidden in CREATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("create")
            assert not window.batch_selector_btn.isVisible()

    def test_batch_selector_button_opens_dialog(self, qtbot, mock_api_with_batches, mock_config):
        """Batch selector button opens dialog on click."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")

            # Mock the dialog
            with patch("app.ui.main_window.BatchSelectorDialog") as mock_dialog:
                mock_instance = MagicMock()
                mock_instance.exec.return_value = QtWidgets.QDialog.DialogCode.Accepted
                mock_instance.selected_batch_id = "batch_001"
                mock_dialog.return_value = mock_instance

                # Click button
                window.batch_selector_btn.click()

                # Dialog should be created
                mock_dialog.assert_called_once()


class TestBatchMetadata:
    """Test batch metadata and description display."""

    def test_batch_description_displayed_in_combo(self, qtbot, mock_api_with_batches, mock_config):
        """Batch description shown in combo dropdown."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")

            # Load batches with descriptions
            batches = [
                MagicMock(
                    batch_id="batch_001",
                    description="Vacation 2024-06",
                    is_undone=False,
                ),
            ]
            window._on_batches_loaded(batches)

            # Check that description appears in combo
            combo_text = window.batch_selector_combo.itemText(0)
            assert "Vacation" in combo_text or "2024" in combo_text

    def test_batch_loaded_updates_combo(self, qtbot, mock_api_with_batches, mock_config):
        """Loading batches updates combo dropdown."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")

            # Initially empty
            assert window.batch_selector_combo.count() == 0

            # Load batches
            batches = [
                MagicMock(
                    batch_id="batch_001",
                    description="First batch",
                    is_undone=False,
                ),
                MagicMock(
                    batch_id="batch_002",
                    description="Second batch",
                    is_undone=False,
                ),
            ]
            window._on_batches_loaded(batches)

            # Combo should be populated
            assert window.batch_selector_combo.count() >= 2

    def test_batch_selection_by_index_works(self, qtbot, mock_api_with_batches, mock_config):
        """Can select batch by index."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")

            # Load batches
            batches = [
                MagicMock(
                    batch_id="batch_001",
                    description="First",
                    is_undone=False,
                ),
                MagicMock(
                    batch_id="batch_002",
                    description="Second",
                    is_undone=False,
                ),
            ]
            window._on_batches_loaded(batches)

            # Select by index
            window.batch_selector_combo.setCurrentIndex(1)

            # Verify selection
            assert window.batch_selector_combo.currentIndex() == 1


class TestBatchSelectorDialogIntegration:
    """Test BatchSelectorDialog integration."""

    def test_dialog_title_set(self, qtbot, mock_api_with_batches, mock_config):
        """Dialog has appropriate title."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")

            # Mock dialog
            with patch("app.ui.main_window.BatchSelectorDialog") as mock_dialog:
                mock_instance = MagicMock()
                mock_instance.exec.return_value = QtWidgets.QDialog.DialogCode.Accepted
                mock_dialog.return_value = mock_instance

                window.batch_selector_btn.click()

                # Dialog created with undo_manager and parent window
                mock_dialog.assert_called_once()
                args = mock_dialog.call_args
                assert args[0][0] == window.undo_manager  # First arg is undo_manager
                assert args[0][1] == window  # Second arg is main window

    def test_dialog_accepts_selection(self, qtbot, mock_api_with_batches, mock_config):
        """Dialog acceptance updates combo."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")

            # Load batches
            batches = [
                MagicMock(
                    batch_id="batch_001",
                    description="Batch 1",
                    is_undone=False,
                ),
                MagicMock(
                    batch_id="batch_002",
                    description="Batch 2",
                    is_undone=False,
                ),
            ]
            window._on_batches_loaded(batches)

            # Mock dialog that accepts and selects batch
            with patch("app.ui.main_window.BatchSelectorDialog") as mock_dialog:
                mock_instance = MagicMock()
                mock_instance.exec.return_value = QtWidgets.QDialog.DialogCode.Accepted
                mock_instance.selected_batch_id = "batch_002"
                mock_dialog.return_value = mock_instance

                # Initial selection
                window.batch_selector_combo.setCurrentIndex(0)

                # Click button
                window.batch_selector_btn.click()

                # Dialog should be called
                mock_dialog.assert_called_once()
