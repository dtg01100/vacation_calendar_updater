"""Tests for TimePickerDialog component."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from PySide6 import QtCore, QtWidgets

from app.ui.time_picker import TimePickerDialog


@pytest.fixture
def qapp():
    """Create QApplication for testing."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture
def time_picker_dialog(qapp):
    """Create a TimePickerDialog instance for testing."""
    dialog = TimePickerDialog()
    yield dialog
    dialog.deleteLater()


class TestTimePickerDialogInitialization:
    """Test TimePickerDialog initialization."""

    def test_dialog_creation(self, time_picker_dialog):
        """Test that dialog can be created."""
        assert time_picker_dialog is not None
        assert isinstance(time_picker_dialog, QtWidgets.QDialog)

    def test_dialog_is_modal(self, time_picker_dialog):
        """Test that dialog is modal."""
        assert time_picker_dialog.isModal() is True

    def test_dialog_title(self, time_picker_dialog):
        """Test that dialog has correct title."""
        assert time_picker_dialog.windowTitle() == "Select Time"

    def test_dialog_minimum_width(self, time_picker_dialog):
        """Test that dialog has minimum width."""
        assert time_picker_dialog.minimumWidth() == 250

    def test_default_time_initialization(self, time_picker_dialog):
        """Test that default time is current time."""
        current_time = QtCore.QTime.currentTime()
        selected_time = time_picker_dialog.get_selected_time()
        
        # Allow larger tolerance for test execution time
        assert abs(current_time.secsTo(selected_time)) <= 30

    def test_custom_initial_time(self, qapp):
        """Test initialization with custom initial time."""
        initial_time = QtCore.QTime(14, 30)
        dialog = TimePickerDialog(initial_time=initial_time)
        
        assert dialog.get_selected_time() == initial_time
        
        dialog.deleteLater()

    def test_hour_spinbox_exists(self, time_picker_dialog):
        """Test that hour spinbox exists."""
        assert hasattr(time_picker_dialog, 'hour_spinbox')
        assert time_picker_dialog.hour_spinbox is not None

    def test_minute_spinbox_exists(self, time_picker_dialog):
        """Test that minute spinbox exists."""
        assert hasattr(time_picker_dialog, 'minute_spinbox')
        assert time_picker_dialog.minute_spinbox is not None

    def test_selected_time_display_exists(self, time_picker_dialog):
        """Test that selected time display label exists."""
        assert hasattr(time_picker_dialog, 'selected_time_display')
        assert time_picker_dialog.selected_time_display is not None


class TestTimePickerHourSpinbox:
    """Test hour spinbox functionality."""

    def test_hour_spinbox_range(self, time_picker_dialog):
        """Test that hour spinbox has correct range."""
        assert time_picker_dialog.hour_spinbox.minimum() == 0
        assert time_picker_dialog.hour_spinbox.maximum() == 23

    def test_hour_spinbox_value_initialization(self, qapp):
        """Test that hour spinbox is initialized correctly."""
        test_time = QtCore.QTime(15, 45)
        dialog = TimePickerDialog(initial_time=test_time)
        
        assert dialog.hour_spinbox.value() == 15
        
        dialog.deleteLater()

    def test_hour_spinbox_set_value_min(self, time_picker_dialog):
        """Test setting hour to minimum."""
        time_picker_dialog.hour_spinbox.setValue(0)
        assert time_picker_dialog.hour_spinbox.value() == 0
        assert time_picker_dialog.get_selected_time().hour() == 0

    def test_hour_spinbox_set_value_max(self, time_picker_dialog):
        """Test setting hour to maximum."""
        time_picker_dialog.hour_spinbox.setValue(23)
        assert time_picker_dialog.hour_spinbox.value() == 23
        assert time_picker_dialog.get_selected_time().hour() == 23

    def test_hour_spinbox_set_value_mid(self, time_picker_dialog):
        """Test setting hour to mid-range."""
        time_picker_dialog.hour_spinbox.setValue(12)
        assert time_picker_dialog.hour_spinbox.value() == 12
        assert time_picker_dialog.get_selected_time().hour() == 12

    def test_hour_spinbox_increment(self, time_picker_dialog):
        """Test incrementing hour value."""
        time_picker_dialog.hour_spinbox.setValue(5)
        time_picker_dialog.hour_spinbox.setValue(6)
        assert time_picker_dialog.hour_spinbox.value() == 6

    def test_hour_spinbox_wrapping_at_boundary(self, time_picker_dialog):
        """Test hour wrapping behavior (no wrapping by default)."""
        time_picker_dialog.hour_spinbox.setValue(23)
        # Qt spinbox doesn't wrap by default
        time_picker_dialog.hour_spinbox.stepUp()
        # Should be clamped at maximum
        assert time_picker_dialog.hour_spinbox.value() == 23


class TestTimePickerMinuteSpinbox:
    """Test minute spinbox functionality."""

    def test_minute_spinbox_range(self, time_picker_dialog):
        """Test that minute spinbox has correct range."""
        assert time_picker_dialog.minute_spinbox.minimum() == 0
        assert time_picker_dialog.minute_spinbox.maximum() == 59

    def test_minute_spinbox_value_initialization(self, qapp):
        """Test that minute spinbox is initialized correctly."""
        test_time = QtCore.QTime(15, 45)
        dialog = TimePickerDialog(initial_time=test_time)
        
        assert dialog.minute_spinbox.value() == 45
        
        dialog.deleteLater()

    def test_minute_spinbox_set_value_min(self, time_picker_dialog):
        """Test setting minute to minimum."""
        time_picker_dialog.minute_spinbox.setValue(0)
        assert time_picker_dialog.minute_spinbox.value() == 0
        assert time_picker_dialog.get_selected_time().minute() == 0

    def test_minute_spinbox_set_value_max(self, time_picker_dialog):
        """Test setting minute to maximum."""
        time_picker_dialog.minute_spinbox.setValue(59)
        assert time_picker_dialog.minute_spinbox.value() == 59
        assert time_picker_dialog.get_selected_time().minute() == 59

    def test_minute_spinbox_set_value_mid(self, time_picker_dialog):
        """Test setting minute to mid-range."""
        time_picker_dialog.minute_spinbox.setValue(30)
        assert time_picker_dialog.minute_spinbox.value() == 30
        assert time_picker_dialog.get_selected_time().minute() == 30

    def test_minute_spinbox_increment(self, time_picker_dialog):
        """Test incrementing minute value."""
        time_picker_dialog.minute_spinbox.setValue(10)
        time_picker_dialog.minute_spinbox.setValue(11)
        assert time_picker_dialog.minute_spinbox.value() == 11


class TestTimePickerGetSelectedTime:
    """Test get_selected_time functionality."""

    def test_get_selected_time_returns_qtime(self, time_picker_dialog):
        """Test that get_selected_time returns QTime object."""
        result = time_picker_dialog.get_selected_time()
        assert isinstance(result, QtCore.QTime)

    def test_get_selected_time_default(self, qapp):
        """Test get_selected_time with default current time."""
        dialog = TimePickerDialog()
        current_time = QtCore.QTime.currentTime()
        selected_time = dialog.get_selected_time()
        
        # Allow larger tolerance for test execution
        assert abs(current_time.secsTo(selected_time)) <= 30
        
        dialog.deleteLater()

    def test_get_selected_time_custom(self, qapp):
        """Test get_selected_time with custom initial time."""
        custom_time = QtCore.QTime(10, 45)
        dialog = TimePickerDialog(initial_time=custom_time)
        
        selected = dialog.get_selected_time()
        assert selected.hour() == 10
        assert selected.minute() == 45
        
        dialog.deleteLater()

    def test_get_selected_time_after_hour_change(self, time_picker_dialog):
        """Test get_selected_time after hour is changed."""
        time_picker_dialog.hour_spinbox.setValue(14)
        selected = time_picker_dialog.get_selected_time()
        
        assert selected.hour() == 14

    def test_get_selected_time_after_minute_change(self, time_picker_dialog):
        """Test get_selected_time after minute is changed."""
        time_picker_dialog.minute_spinbox.setValue(30)
        selected = time_picker_dialog.get_selected_time()
        
        assert selected.minute() == 30

    def test_get_selected_time_after_both_changes(self, time_picker_dialog):
        """Test get_selected_time after both hour and minute are changed."""
        time_picker_dialog.hour_spinbox.setValue(16)
        time_picker_dialog.minute_spinbox.setValue(45)
        
        selected = time_picker_dialog.get_selected_time()
        assert selected.hour() == 16
        assert selected.minute() == 45


class TestTimePickerTimeDisplay:
    """Test time display update functionality."""

    def test_time_display_label_exists(self, time_picker_dialog):
        """Test that time display label exists."""
        assert time_picker_dialog.selected_time_display is not None

    def test_time_display_format_after_hour_change(self, time_picker_dialog):
        """Test that time display updates when hour changes."""
        time_picker_dialog.hour_spinbox.setValue(9)
        
        text = time_picker_dialog.selected_time_display.text()
        assert "09:" in text or "9:" in text

    def test_time_display_format_after_minute_change(self, time_picker_dialog):
        """Test that time display updates when minute changes."""
        time_picker_dialog.minute_spinbox.setValue(5)
        
        text = time_picker_dialog.selected_time_display.text()
        assert ":05" in text

    def test_time_display_format_padded(self, time_picker_dialog):
        """Test that time display is properly formatted with padding."""
        time_picker_dialog.hour_spinbox.setValue(8)
        time_picker_dialog.minute_spinbox.setValue(5)
        
        text = time_picker_dialog.selected_time_display.text()
        # Should be "08:05" format (zero-padded)
        assert "08:05" in text


class TestTimePickerEdgeCases:
    """Test TimePickerDialog edge cases."""

    def test_midnight(self, qapp):
        """Test midnight time."""
        midnight = QtCore.QTime(0, 0)
        dialog = TimePickerDialog(initial_time=midnight)
        
        assert dialog.get_selected_time() == midnight
        
        dialog.deleteLater()

    def test_noon(self, qapp):
        """Test noon time."""
        noon = QtCore.QTime(12, 0)
        dialog = TimePickerDialog(initial_time=noon)
        
        assert dialog.get_selected_time() == noon
        
        dialog.deleteLater()

    def test_end_of_day(self, qapp):
        """Test end of day time."""
        end_of_day = QtCore.QTime(23, 59)
        dialog = TimePickerDialog(initial_time=end_of_day)
        
        assert dialog.get_selected_time() == end_of_day
        
        dialog.deleteLater()

    def test_consecutive_changes(self, time_picker_dialog):
        """Test consecutive time changes."""
        time_picker_dialog.hour_spinbox.setValue(5)
        time_picker_dialog.minute_spinbox.setValue(30)
        assert time_picker_dialog.get_selected_time() == QtCore.QTime(5, 30)
        
        time_picker_dialog.hour_spinbox.setValue(10)
        assert time_picker_dialog.get_selected_time() == QtCore.QTime(10, 30)
        
        time_picker_dialog.minute_spinbox.setValue(45)
        assert time_picker_dialog.get_selected_time() == QtCore.QTime(10, 45)

    def test_parent_widget_initialization(self, qapp):
        """Test initialization with parent widget."""
        parent = QtWidgets.QWidget()
        dialog = TimePickerDialog(parent=parent)
        
        assert dialog.parent() == parent
        
        dialog.deleteLater()
        parent.deleteLater()

    def test_dialog_accept_functionality(self, time_picker_dialog):
        """Test dialog accept functionality."""
        time_picker_dialog.hour_spinbox.setValue(15)
        time_picker_dialog.minute_spinbox.setValue(30)
        
        # Dialog should accept with the correct time
        selected_time = time_picker_dialog.get_selected_time()
        assert selected_time == QtCore.QTime(15, 30)

    def test_multiple_dialogs(self, qapp):
        """Test creating multiple dialog instances."""
        dialog1 = TimePickerDialog(initial_time=QtCore.QTime(10, 0))
        dialog2 = TimePickerDialog(initial_time=QtCore.QTime(15, 30))
        
        assert dialog1.get_selected_time() == QtCore.QTime(10, 0)
        assert dialog2.get_selected_time() == QtCore.QTime(15, 30)
        
        dialog1.deleteLater()
        dialog2.deleteLater()

    def test_time_display_consistency(self, time_picker_dialog):
        """Test that time display is consistent with spinbox values."""
        for hour in [0, 6, 12, 18, 23]:
            for minute in [0, 15, 30, 45, 59]:
                time_picker_dialog.hour_spinbox.setValue(hour)
                time_picker_dialog.minute_spinbox.setValue(minute)
                
                selected = time_picker_dialog.get_selected_time()
                assert selected.hour() == hour
                assert selected.minute() == minute
