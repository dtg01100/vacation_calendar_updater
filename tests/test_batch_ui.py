from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtWidgets

from app.ui.main_window import MainWindow


def _build_window(qtbot):
    api = MagicMock()
    api.get_calendars.return_value = []
    config = MagicMock()
    config.ensure_defaults.return_value = MagicMock(
        email_address="test@example.com",
        calendar="Primary",
        weekdays={"monday": True},
        send_email=True,
    )

    with patch("app.ui.main_window.StartupWorker"):
        window = MainWindow(api=api, config=config)
        window.calendar_names = ["Primary"]
        window.calendar_id_by_name = {"Primary": "cal_001"}
        qtbot.addWidget(window)
        window.show()
        return window


class TestModeUiStates:
    def test_update_mode_shows_batch_selector_and_message(self, qtbot):
        window = _build_window(qtbot)
        window.undo_manager.get_undoable_batches = lambda: []

        window._switch_mode("update")

        assert window.batch_selector_btn.isVisible()
        assert window.batch_summary_label.isVisible()
        assert "batch" in window.validation_status.text().lower()
        assert window.process_button.text() == "Update Events"

    def test_delete_mode_hides_form_fields(self, qtbot):
        window = _build_window(qtbot)
        window.undo_manager.get_undoable_batches = lambda: []

        window._switch_mode("delete")

        assert not window.event_name.isVisible()
        assert not window.notification_email.isVisible()
        assert window.batch_selector_btn.isVisible()
        assert window.process_button.text() == "Delete Events"

    def test_switch_mode_resets_selected_batch(self, qtbot):
        window = _build_window(qtbot)
        window.selected_batch_for_operation = "batch-1"

        window._switch_mode("create")

        assert window.selected_batch_for_operation is None
        assert window.batch_summary_label.text() == ""


class TestValidationByMode:
    def test_update_validation_requires_batch(self, qtbot, monkeypatch):
        window = _build_window(qtbot)
        window.current_mode = "update"
        window._switch_mode("update")

        # Provide a valid request but no selected batch
        monkeypatch.setattr("app.ui.main_window.validate_request", lambda _r: [])
        monkeypatch.setattr(window, "_collect_request", lambda: MagicMock())
        monkeypatch.setattr(window, "_creation_running", lambda: False)

        window._update_validation()

        assert window.process_button.isEnabled() is False
        assert "select" in window.validation_status.text().lower()

    def test_delete_validation_requires_batch(self, qtbot):
        window = _build_window(qtbot)
        window.current_mode = "delete"
        window._switch_mode("delete")

        window._update_validation()

        assert window.process_button.isEnabled() is False
        assert "select" in window.validation_status.text().lower()
