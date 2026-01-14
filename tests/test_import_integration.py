"""End-to-end integration tests for import mode."""
from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtWidgets

from app.ui.main_window import MainWindow
from app.services import EnhancedCreatedEvent


@pytest.fixture
def mock_api():
    api = MagicMock()
    api.get_calendars.return_value = []
    return api


@pytest.fixture
def mock_config():
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


def _build_window(qtbot, mock_api, mock_config):
    with patch("app.ui.main_window.StartupWorker"):
        window = MainWindow(api=mock_api, config=mock_config)
        window.calendar_names = ["Primary"]
        window.calendar_id_by_name = {"Primary": "cal_001"}
        qtbot.addWidget(window)
        window.show()
        return window


class TestImportMode:
    """Test import mode UI switching and visibility."""

    def test_import_mode_shows_import_controls(self, qtbot, mock_api, mock_config):
        window = _build_window(qtbot, mock_api, mock_config)
        
        # Initially in create mode
        assert not window.import_controls_frame.isVisible()
        
        # Switch to import mode
        window._switch_mode("import")
        
        # Import controls should now be visible
        assert window.import_controls_frame.isVisible()
        assert not window.batch_selector_btn.isVisible()

    def test_import_mode_hides_batch_selector(self, qtbot, mock_api, mock_config):
        window = _build_window(qtbot, mock_api, mock_config)
        
        window._switch_mode("import")
        
        # Batch selector should be hidden in import mode
        assert not window.batch_selector_btn.isVisible()
        assert not window.batch_summary_label.isVisible()

    def test_import_mode_resets_list_on_entry(self, qtbot, mock_api, mock_config):
        window = _build_window(qtbot, mock_api, mock_config)
        
        # Add dummy items to list
        window.import_list.addItem("Old item 1")
        window.import_list.addItem("Old item 2")
        window.import_status_label.setText("Previous status")
        
        # Switch to import mode
        window._switch_mode("import")
        
        # List should be cleared and status reset
        assert window.import_list.count() == 0
        assert window.import_status_label.text() == "Idle"

    def test_other_modes_hide_import_controls(self, qtbot, mock_api, mock_config):
        window = _build_window(qtbot, mock_api, mock_config)
        
        # Switch to import mode first
        window._switch_mode("import")
        assert window.import_controls_frame.isVisible()
        
        # Switch to create mode
        window._switch_mode("create")
        assert not window.import_controls_frame.isVisible()
        
        # Switch to update mode
        window._switch_mode("update")
        assert not window.import_controls_frame.isVisible()
        
        # Switch to delete mode
        window._switch_mode("delete")
        assert not window.import_controls_frame.isVisible()


class TestImportBatching:
    """Test event batching logic."""

    def test_group_events_by_summary(self, qtbot, mock_api, mock_config):
        window = _build_window(qtbot, mock_api, mock_config)
        
        items = [
            {
                "id": "e1",
                "summary": "Vacation",
                "start": {"dateTime": "2024-01-15T09:00:00Z"},
                "end": {"dateTime": "2024-01-15T10:00:00Z"},
            },
            {
                "id": "e2",
                "summary": "Vacation",
                "start": {"dateTime": "2024-01-16T09:00:00Z"},
                "end": {"dateTime": "2024-01-16T10:00:00Z"},
            },
        ]
        
        batches = window._group_events_into_batches(items, "cal_001")
        
        # Should group by summary
        assert len(batches) > 0
        assert all("description" in b and "events" in b for b in batches)

    def test_group_events_handles_all_day_events(self, qtbot, mock_api, mock_config):
        window = _build_window(qtbot, mock_api, mock_config)
        
        items = [
            {
                "id": "e1",
                "summary": "Holiday",
                "start": {"date": "2024-01-01"},
                "end": {"date": "2024-01-02"},
            },
        ]
        
        batches = window._group_events_into_batches(items, "cal_001")
        
        # Should not crash and should produce batches
        assert len(batches) > 0
        assert batches[0]["event_count"] == 1

    def test_group_events_skips_missing_fields(self, qtbot, mock_api, mock_config):
        window = _build_window(qtbot, mock_api, mock_config)
        
        items = [
            {
                "id": "e1",
                "summary": "Event1",
                "start": {"dateTime": "2024-01-15T09:00:00Z"},
                # Missing end
            },
            {
                "id": "e2",
                "summary": "Event2",
                "start": {"dateTime": "2024-01-16T09:00:00Z"},
                "end": {"dateTime": "2024-01-16T10:00:00Z"},
            },
        ]
        
        batches = window._group_events_into_batches(items, "cal_001")
        
        # Should handle missing fields gracefully
        # At least event2 should be included
        assert any(b for b in batches if b["event_count"] >= 1)

    def test_group_events_splits_by_gap(self, qtbot, mock_api, mock_config):
        window = _build_window(qtbot, mock_api, mock_config)
        
        items = [
            {
                "id": "e1",
                "summary": "Trip",
                "start": {"date": "2024-01-01"},
                "end": {"date": "2024-01-02"},
            },
            {
                "id": "e2",
                "summary": "Trip",
                "start": {"date": "2024-01-10"},  # 9 days later, should create separate batch
                "end": {"date": "2024-01-11"},
            },
        ]
        
        batches = window._group_events_into_batches(items, "cal_001")
        
        # Should create separate batches due to gap > 3 days
        assert len(batches) >= 2


class TestImportFlow:
    """Test the full import fetch and selection flow."""

    def test_selected_import_batches_returns_checked_items(
        self, qtbot, mock_api, mock_config
    ):
        window = _build_window(qtbot, mock_api, mock_config)
        
        # Simulate fetched batches
        event1 = EnhancedCreatedEvent(
            event_id="e1",
            calendar_id="cal_001",
            event_name="Event 1",
            start_time=dt.datetime(2024, 1, 15, 9, 0),
            end_time=dt.datetime(2024, 1, 15, 10, 0),
            created_at=dt.datetime.now(),
            batch_id="",
            request_snapshot=None,
        )
        
        event2 = EnhancedCreatedEvent(
            event_id="e2",
            calendar_id="cal_001",
            event_name="Event 2",
            start_time=dt.datetime(2024, 2, 15, 9, 0),
            end_time=dt.datetime(2024, 2, 15, 10, 0),
            created_at=dt.datetime.now(),
            batch_id="",
            request_snapshot=None,
        )
        
        window.import_batches = [
            {"description": "Batch 1", "events": [event1], "event_count": 1},
            {"description": "Batch 2", "events": [event2], "event_count": 1},
        ]
        
        # Populate list with checked items
        from PySide6 import QtCore
        for i, batch in enumerate(window.import_batches):
            item = QtWidgets.QListWidgetItem(
                f"{batch['description']} - {batch['event_count']} event(s)"
            )
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked)
            item.setData(QtCore.Qt.UserRole, i)
            window.import_list.addItem(item)
        
        selected = window._selected_import_batches()
        
        # Both batches should be selected
        assert len(selected) == 2
        assert selected[0]["description"] == "Batch 1"
        assert selected[1]["description"] == "Batch 2"

    def test_selected_import_batches_respects_checkbox_state(
        self, qtbot, mock_api, mock_config
    ):
        window = _build_window(qtbot, mock_api, mock_config)
        
        event1 = EnhancedCreatedEvent(
            event_id="e1",
            calendar_id="cal_001",
            event_name="Event 1",
            start_time=dt.datetime(2024, 1, 15, 9, 0),
            end_time=dt.datetime(2024, 1, 15, 10, 0),
            created_at=dt.datetime.now(),
            batch_id="",
            request_snapshot=None,
        )
        
        window.import_batches = [
            {"description": "Batch 1", "events": [event1], "event_count": 1},
        ]
        
        # Add item and uncheck it
        from PySide6 import QtCore
        item = QtWidgets.QListWidgetItem("Batch 1 - 1 event(s)")
        item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
        item.setCheckState(QtCore.Qt.Unchecked)  # Explicitly unchecked
        item.setData(QtCore.Qt.UserRole, 0)
        window.import_list.addItem(item)
        
        selected = window._selected_import_batches()
        
        # Should be empty since batch is unchecked
        assert len(selected) == 0

    def test_import_batches_adds_to_undo_manager(self, qtbot, mock_api, mock_config):
        window = _build_window(qtbot, mock_api, mock_config)
        
        event1 = EnhancedCreatedEvent(
            event_id="e1",
            calendar_id="cal_001",
            event_name="Event 1",
            start_time=dt.datetime(2024, 1, 15, 9, 0),
            end_time=dt.datetime(2024, 1, 15, 10, 0),
            created_at=dt.datetime.now(),
            batch_id="",
            request_snapshot=None,
        )
        
        window.import_batches = [
            {"description": "Batch 1", "events": [event1], "event_count": 1},
        ]
        
        # Populate list with checked items
        from PySide6 import QtCore
        item = QtWidgets.QListWidgetItem("Batch 1 - 1 event(s)")
        item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
        item.setCheckState(QtCore.Qt.Checked)
        item.setData(QtCore.Qt.UserRole, 0)
        window.import_list.addItem(item)
        
        # Mock the undo manager to track calls
        with patch.object(window.undo_manager, "add_operation") as mock_add:
            with patch.object(window.undo_manager, "save_history"):
                with patch.object(
                    window, "_update_undo_ui"
                ):
                    with patch("PySide6.QtWidgets.QMessageBox.information"):
                        window._import_batches()
                        
                        # Should have called add_operation
                        mock_add.assert_called_once()
                        call_kwargs = mock_add.call_args[1]
                        assert call_kwargs["operation_type"] == "create"
                        assert len(call_kwargs["event_snapshots"]) == 1
