import pytest
from PySide6 import QtCore, QtWidgets

from app.config import ConfigManager
from app.ui.main_window import MainWindow


class DummyApi:
    def user_email(self):
        return ""

    def list_calendars(self):
        return [], []

    def create_event(
        self, *args, **kwargs
    ):  # pragma: no cover - not used in these tests
        raise AssertionError("create_event should not be called in this test")

    def delete_event(
        self, *args, **kwargs
    ):  # pragma: no cover - not used in these tests
        raise AssertionError("delete_event should not be called in this test")

    def send_email(self, *args, **kwargs):  # pragma: no cover - not used in these tests
        return None


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture(autouse=True)
def _prevent_startup_worker(monkeypatch):
    """Avoid starting background threads during UI-focused tests."""
    monkeypatch.setattr("PySide6.QtCore.QThread.start", lambda self: None)


def test_end_before_start_moves_start_back(qapp, tmp_path):
    window = MainWindow(DummyApi(), ConfigManager(tmp_path / "config.cfg"))

    window.start_date.setDate(QtCore.QDate(2024, 1, 10))
    window.end_date.setDate(QtCore.QDate(2024, 1, 15))

    new_end = QtCore.QDate(2024, 1, 5)
    window.end_date.setDate(new_end)

    assert window.start_date.date() == new_end
    assert window.end_date.date() == new_end


def test_start_after_end_moves_end_forward(qapp, tmp_path):
    window = MainWindow(DummyApi(), ConfigManager(tmp_path / "config.cfg"))

    window.start_date.setDate(QtCore.QDate(2024, 1, 5))
    window.end_date.setDate(QtCore.QDate(2024, 1, 5))

    later_start = QtCore.QDate(2024, 1, 20)
    window.start_date.setDate(later_start)

    assert window.end_date.date() == later_start
    assert window.start_date.date() == later_start
