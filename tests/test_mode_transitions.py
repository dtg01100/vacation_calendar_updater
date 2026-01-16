"""Tests for mode transitions and state preservation."""
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
        last_start_time="08:00",  # Add the missing last_start_time attribute
        time_presets=["08:00", "09:00", "12:00", "13:00", "14:00", "17:00"],  # Add time_presets attribute
        last_day_length="08:00",  # Add the missing last_day_length attribute
    )
    return config


@pytest.fixture
def mock_api_with_batches():
    """Create mock GoogleApi with batch operations."""
    api = MagicMock()
    api.get_calendars.return_value = [("Primary", "cal_001")]
    return api


class TestModeTransitions:
    """Test transitions between modes."""

    def test_switch_create_to_update_mode(self, qtbot, mock_api_with_batches, mock_config):
        """Switching from CREATE to UPDATE shows batch selector."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            # Start in CREATE mode
            window._switch_mode("create")
            assert not window.batch_selector_btn.isVisible()

            # Switch to UPDATE
            window._switch_mode("update")
            assert window.batch_selector_btn.isVisible()

    def test_switch_create_to_delete_mode(self, qtbot, mock_api_with_batches, mock_config):
        """Switching from CREATE to DELETE shows batch selector."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            # Start in CREATE mode
            window._switch_mode("create")
            assert not window.batch_selector_btn.isVisible()

            # Switch to DELETE
            window._switch_mode("delete")
            assert window.batch_selector_btn.isVisible()

    def test_mode_buttons_toggle_correctly(self, qtbot, mock_api, mock_config):
        """Mode buttons toggle on/off correctly."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            # CREATE mode
            window._switch_mode("create")
            assert window.mode_create_btn.isChecked()
            assert not window.mode_update_btn.isChecked()
            assert not window.mode_delete_btn.isChecked()

            # UPDATE mode
            window._switch_mode("update")
            assert not window.mode_create_btn.isChecked()
            assert window.mode_update_btn.isChecked()
            assert not window.mode_delete_btn.isChecked()

            # DELETE mode
            window._switch_mode("delete")
            assert not window.mode_create_btn.isChecked()
            assert not window.mode_update_btn.isChecked()
            assert window.mode_delete_btn.isChecked()


class TestFieldPersistence:
    """Test that form fields persist across mode switches."""

    def test_create_to_update_preserves_form_values(self, qtbot, mock_api_with_batches, mock_config):
        """Switching CREATE→UPDATE preserves form field values."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            # Set form values in CREATE
            window._switch_mode("create")
            window.event_name.setText("My Vacation")
            window.notification_email.setText("user@example.com")

            # Save values
            saved_event_name = window.event_name.text()
            saved_email = window.notification_email.text()
            saved_calendar = window._get_current_calendar()

            # Switch to UPDATE
            window._switch_mode("update")

            # Verify values preserved
            assert window.event_name.text() == saved_event_name
            assert window.notification_email.text() == saved_email
            assert window._get_current_calendar() == saved_calendar

    def test_update_to_create_preserves_form_values(self, qtbot, mock_api_with_batches, mock_config):
        """Switching UPDATE→CREATE preserves form field values."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            # Set form values in UPDATE
            window._switch_mode("update")
            window.event_name.setText("Updated Event")
            window.notification_email.setText("updated@example.com")

            saved_event_name = window.event_name.text()
            saved_email = window.notification_email.text()

            # Switch to CREATE
            window._switch_mode("create")

            # Verify values preserved
            assert window.event_name.text() == saved_event_name
            assert window.notification_email.text() == saved_email


class TestScheduleFieldVisibility:
    """Test schedule field visibility changes per mode."""

    def test_create_mode_all_schedule_fields_visible(self, qtbot, mock_api, mock_config):
        """All schedule fields visible in CREATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("create")

            # All schedule fields visible
            assert window.event_name.isVisible()
            assert window.notification_email.isVisible()
            assert window.start_date.isVisible()
            assert window.end_date.isVisible()
            assert window.hour_spinbox.isVisible()
            assert window.minute_spinbox.isVisible()
            assert window.day_length_hour_spinbox.isVisible()

    def test_update_mode_all_schedule_fields_visible(self, qtbot, mock_api_with_batches, mock_config):
        """All schedule fields visible in UPDATE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("update")

            # All schedule fields visible
            assert window.event_name.isVisible()
            assert window.notification_email.isVisible()
            assert window.start_date.isVisible()
            assert window.end_date.isVisible()
            assert window.hour_spinbox.isVisible()
            assert window.minute_spinbox.isVisible()
            assert window.day_length_hour_spinbox.isVisible()

    def test_delete_mode_schedule_fields_hidden(self, qtbot, mock_api_with_batches, mock_config):
        """Schedule fields hidden in DELETE mode."""
        with patch("app.ui.main_window.StartupWorker"):
            window = MainWindow(api=mock_api_with_batches, config=mock_config)
            window.calendar_names = ["Primary"]
            window.calendar_id_by_name = {"Primary": "cal_001"}
            qtbot.addWidget(window)
            window.show()

            window._switch_mode("delete")

            # Schedule fields should be hidden
            assert not window.event_name.isVisible()
            assert not window.start_date.isVisible()
            assert not window.end_date.isVisible()
            assert not window.hour_spinbox.isVisible()
            assert not window.minute_spinbox.isVisible()
            assert not window.day_length_hour_spinbox.isVisible()
