import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import fixtures from fixtures package for discovery
from tests.fixtures.mock_api import empty_api, mock_api, mockable_api  # noqa: F401
from tests.fixtures.sample_data import (  # noqa: F401
    sample_batch,
    sample_event,
    sample_schedule_request,
    sample_schedule_request_custom_hours,
    sample_schedule_request_single_day,
)


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for the test session."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def undo_manager():
    """Create a fresh UndoManager for testing.

    Returns a new UndoManager instance with empty stacks.
    Optionally accepts initial batches for pre-populated testing.
    """
    from app.undo_manager import UndoManager

    manager = UndoManager()
    return manager


@pytest.fixture
def mock_config():
    """Create a mock Config object for testing."""
    from unittest.mock import MagicMock

    config = MagicMock()
    config.get_calendar_name.return_value = "Primary"
    config.get_calendar_id.return_value = "cal_primary"
    config.get_default_day_length.return_value = 8.0
    config.get_notification_email.return_value = "[REDACTED]"
    return config


class QtBot:
    """Simple QtBot replacement for testing without pytest-qt plugin."""

    def __init__(self, qapp):
        self.qapp = qapp
        self.widgets = []

    def addWidget(self, widget):
        """Track a widget for cleanup."""
        self.widgets.append(widget)
        return widget

    def waitSignal(self, signal, timeout=1000):
        """Wait for a signal to be emitted."""
        from PySide6.QtCore import QEventLoop, QTimer

        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(timeout)

        class SignalWaiter:
            def __init__(self):
                self.args = None
                self.called = False

            def __enter__(self):
                signal.connect(self._on_signal)
                return self

            def __exit__(self, *args):
                try:
                    signal.disconnect(self._on_signal)
                except Exception:
                    pass
                timer.stop()
                loop.quit()

            def _on_signal(self, *args):
                self.args = args
                self.called = True
                timer.stop()
                loop.quit()

        waiter = SignalWaiter()
        waiter.__enter__()
        return waiter

    def cleanup(self):
        """Clean up all tracked widgets."""
        for widget in self.widgets:
            try:
                # Ensure any background processing is stopped cleanly.
                widget.close()
                widget.deleteLater()
            except Exception:
                pass
        self.widgets.clear()


@pytest.fixture
def qtbot(qapp):
    """Provide a qtbot fixture similar to pytest-qt."""
    bot = QtBot(qapp)
    yield bot
    bot.cleanup()
