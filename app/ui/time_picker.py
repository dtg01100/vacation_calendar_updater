"""Advanced time picker dialog for vacation calendar."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from . import dark_mode


class TimePickerDialog(QtWidgets.QDialog):
    """Modal dialog for advanced time selection with hour and minute spinners."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        initial_time: QtCore.QTime | None = None,
    ) -> None:
        """Initialize the time picker dialog.

        Args:
            parent: Parent widget
            initial_time: Initial time to display (defaults to current time)
        """
        super().__init__(parent)
        self.setWindowTitle("Select Time")
        self.setModal(True)
        self.setMinimumWidth(250)

        if initial_time is None:
            now = QtCore.QTime.currentTime()
            # Round to nearest minute to keep the default selection aligned with current time
            if now.second() > 30:
                initial_time = now.addSecs(60 - now.second())
            else:
                initial_time = now.addSecs(-now.second())
        self._setup_ui(initial_time)

    def _setup_ui(self, initial_time: QtCore.QTime) -> None:
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout()

        # Current time display
        current_time_label = QtWidgets.QLabel()
        current_time_label.setText(
            f"Current selection: {initial_time.toString('HH:mm')}"
        )
        current_time_label.setStyleSheet(
            f"font-weight: bold; font-size: {dark_mode.FONT_SIZE_MEDIUM}px;"
        )
        layout.addWidget(current_time_label)

        # Time selection layout
        time_layout = QtWidgets.QHBoxLayout()

        # Hour spinbox
        hour_label = QtWidgets.QLabel("Hour:")
        self.hour_spinbox = QtWidgets.QSpinBox()
        self.hour_spinbox.setMinimum(0)
        self.hour_spinbox.setMaximum(23)
        self.hour_spinbox.setValue(initial_time.hour())
        self.hour_spinbox.setMinimumWidth(60)
        self.hour_spinbox.valueChanged.connect(self._on_time_changed)

        time_layout.addWidget(hour_label)
        time_layout.addWidget(self.hour_spinbox)

        # Separator
        separator = QtWidgets.QLabel(":")
        separator.setStyleSheet("font-weight: bold;")
        time_layout.addWidget(separator)

        # Minute spinbox
        minute_label = QtWidgets.QLabel("Minute:")
        self.minute_spinbox = QtWidgets.QSpinBox()
        self.minute_spinbox.setMinimum(0)
        self.minute_spinbox.setMaximum(59)
        self.minute_spinbox.setValue(initial_time.minute())
        self.minute_spinbox.setMinimumWidth(60)
        self.minute_spinbox.valueChanged.connect(self._on_time_changed)

        time_layout.addWidget(minute_label)
        time_layout.addWidget(self.minute_spinbox)
        time_layout.addStretch()

        layout.addLayout(time_layout)

        # Display selected time
        self.selected_time_display = QtWidgets.QLabel()
        colors = dark_mode.get_colors()
        self.selected_time_display.setStyleSheet(
            f"font-size: {dark_mode.FONT_SIZE_LARGE}px; font-weight: bold; color: {colors['button_checked']};"
        )
        self._update_time_display()
        layout.addWidget(self.selected_time_display)

        # Button box
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def _on_time_changed(self) -> None:
        """Update the time display when spinboxes change."""
        self._update_time_display()

    def _update_time_display(self) -> None:
        """Update the selected time display label."""
        hour = self.hour_spinbox.value()
        minute = self.minute_spinbox.value()
        time_str = f"{hour:02d}:{minute:02d}"
        self.selected_time_display.setText(f"Selected time: {time_str}")

    def get_selected_time(self) -> QtCore.QTime:
        """Return the selected time as a QTime object.

        Returns:
            QTime object with the selected hour and minute
        """
        return QtCore.QTime(self.hour_spinbox.value(), self.minute_spinbox.value())
