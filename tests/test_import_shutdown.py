"""Import mode thread shutdown safety tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtGui, QtWidgets

from app.ui.main_window import MainWindow


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


def test_closeEvent_stops_running_import_thread(qtbot, mock_api, mock_config):
    window = _build_window(qtbot, mock_api, mock_config)

    fake_thread = MagicMock()
    fake_thread.isRunning.return_value = True
    fake_thread.wait.return_value = True

    fake_worker = MagicMock()

    window.import_thread = fake_thread
    window.import_worker = fake_worker

    event = QtGui.QCloseEvent()
    window.closeEvent(event)

    fake_worker.stop.assert_called_once()
    fake_thread.quit.assert_called_once()
    fake_thread.wait.assert_called_once()


def test_closeEvent_skips_stopped_import_thread(qtbot, mock_api, mock_config):
    window = _build_window(qtbot, mock_api, mock_config)

    fake_thread = MagicMock()
    fake_thread.isRunning.return_value = False
    fake_thread.wait.return_value = True

    fake_worker = MagicMock()

    window.import_thread = fake_thread
    window.import_worker = fake_worker

    event = QtGui.QCloseEvent()
    window.closeEvent(event)

    fake_worker.stop.assert_not_called()
    fake_thread.quit.assert_not_called()
    # wait should not be called when not running
    fake_thread.wait.assert_not_called()


def test_about_to_quit_invokes_stop_all_threads(qtbot, mock_api, mock_config):
    window = _build_window(qtbot, mock_api, mock_config)

    app = QtWidgets.QApplication.instance()
    assert app is not None

    with patch.object(window, "_stop_all_threads") as stop_all:
        app.aboutToQuit.emit()
        stop_all.assert_called_once()
