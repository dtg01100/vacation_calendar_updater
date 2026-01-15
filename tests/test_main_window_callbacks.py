from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtWidgets

from app.config import Settings
from app.services import EnhancedCreatedEvent
from app.ui.main_window import MainWindow


@pytest.fixture
def mock_api():
    api = MagicMock()
    api.get_calendars.return_value = []
    return api


@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.ensure_defaults.return_value = Settings(
        email_address="",
        calendar="Primary",
        weekdays={"monday": True},
        send_email=True,
    )
    return cfg


def _build_window(qtbot, mock_api, mock_config):
    with patch("app.ui.main_window.StartupWorker"):
        window = MainWindow(api=mock_api, config=mock_config)
        window.calendar_names = ["Primary", "Work"]
        window.calendar_id_by_name = {"Primary": "cal_001", "Work": "cal_002"}
        qtbot.addWidget(window)
        window.show()
        return window


class TestStartupCallbacks:
    def test_on_startup_finished_updates_ui_and_saves_email(
        self, qtbot, mock_api, mock_config
    ):
        window = _build_window(qtbot, mock_api, mock_config)

        save_calls = []
        mock_config.save.side_effect = lambda settings: save_calls.append(settings.email_address)

        result_email = "user@example.com"
        calendar_names = ["Work", "Primary"]
        calendar_items = [
            {"summary": "Work", "id": "cal_002"},
            {"summary": "Primary", "id": "cal_001"},
        ]

        window._on_startup_finished((result_email, (calendar_names, calendar_items)))

        assert window.calendar_combo.count() == 2
        assert window.calendar_combo.currentText() in calendar_names
        assert window.settings.email_address == result_email
        assert result_email in save_calls
        assert window.statusBar().currentMessage() == "Ready"


class TestImportCallbacks:
    def test_on_import_fetch_finished_populates_list(self, qtbot, mock_api, mock_config):
        window = _build_window(qtbot, mock_api, mock_config)

        event = EnhancedCreatedEvent(
            event_id="e1",
            calendar_id="cal_001",
            event_name="Trip",
            start_time=dt.datetime(2024, 1, 1, 9, 0),
            end_time=dt.datetime(2024, 1, 1, 10, 0),
            created_at=dt.datetime.now(),
            batch_id="",
            request_snapshot=None,
        )
        batches = [
            {"description": "Trip batch", "events": [event], "event_count": 1},
            {"description": "Empty batch", "events": [], "event_count": 0},
        ]

        window.import_fetch_button.setEnabled(True)
        window._on_import_fetch_finished(batches)

        assert window.import_fetch_in_progress is False
        assert window.import_fetch_button.isEnabled()
        assert window.import_list.count() == 2
        assert window.import_list.item(0).checkState() == QtCore.Qt.Checked
        assert "batch(es)" in window.import_status_label.text()

    def test_on_import_fetch_error_sets_status_and_message(self, qtbot, mock_api, mock_config):
        window = _build_window(qtbot, mock_api, mock_config)

        errors = []
        with patch("PySide6.QtWidgets.QMessageBox.critical", lambda *_args, **_kw: errors.append(True)):
            window._on_import_fetch_error("boom")

        assert window.import_fetch_in_progress is False
        assert window.import_fetch_button.isEnabled()
        assert window.import_status_label.text() == "Error"
        assert errors

    def test_on_import_thread_finished_resets_refs(self, qtbot, mock_api, mock_config):
        window = _build_window(qtbot, mock_api, mock_config)
        window.import_thread = object()
        window.import_worker = object()

        window._on_import_thread_finished()

        assert window.import_thread is None
        assert window.import_worker is None

    def test_start_import_fetch_warns_without_calendar(self, qtbot, mock_api, mock_config):
        window = _build_window(qtbot, mock_api, mock_config)
        window.calendar_id_by_name = {}

        warnings = []
        with patch("PySide6.QtWidgets.QMessageBox.warning", lambda *_args, **_kw: warnings.append(True)):
            window._start_import_fetch()

        assert warnings
        assert window.import_thread is None


class TestImportSelection:
    def test_selected_import_batches_filters_checked_items(self, qtbot, mock_api, mock_config):
        window = _build_window(qtbot, mock_api, mock_config)

        event = EnhancedCreatedEvent(
            event_id="e1",
            calendar_id="cal_001",
            event_name="Trip",
            start_time=dt.datetime(2024, 1, 1, 9, 0),
            end_time=dt.datetime(2024, 1, 1, 10, 0),
            created_at=dt.datetime.now(),
            batch_id="",
            request_snapshot=None,
        )
        window.import_batches = [
            {"description": "A", "events": [event], "event_count": 1},
            {"description": "B", "events": [event], "event_count": 1},
        ]

        from PySide6 import QtCore

        for i in range(2):
            item = QtWidgets.QListWidgetItem(f"Batch {i}")
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setData(QtCore.Qt.UserRole, i)
            item.setCheckState(QtCore.Qt.Checked if i == 0 else QtCore.Qt.Unchecked)
            window.import_list.addItem(item)

        selected = window._selected_import_batches()
        assert len(selected) == 1
        assert selected[0]["description"] == "A"
