from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

DATE_FORMAT = "yyyy-MM-dd"


class DatePicker(QtWidgets.QDateEdit):
    """Thin wrapper over QDateEdit with calendar popup enabled."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDisplayFormat(DATE_FORMAT)
        self.setCalendarPopup(True)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setGridVisible(True)
        calendar.setWindowFlag(QtCore.Qt.WindowType.Popup)
        self.setCalendarWidget(calendar)
        self.setDate(QtCore.QDate.currentDate())
        self._setup_shortcuts()

    def erase(self) -> None:
        self.clear()

    # region private helpers
    def _select_delta_days(self, delta: int) -> None:
        current = self.date()
        if not current.isValid():
            current = QtCore.QDate.currentDate()
        self.setDate(current.addDays(delta))

    def _step_months(self, delta: int) -> None:
        current = self.date()
        if not current.isValid():
            current = QtCore.QDate.currentDate()
        self.setDate(current.addMonths(delta))

    def _step_years(self, delta: int) -> None:
        current = self.date()
        if not current.isValid():
            current = QtCore.QDate.currentDate()
        self.setDate(current.addYears(delta))

    def _select_today(self) -> None:
        self.setDate(QtCore.QDate.currentDate())

    def _toggle_popup(self) -> None:
        cal = self.calendarWidget()
        if cal.isVisible():
            cal.hide()
            return
        cal.setSelectedDate(
            self.date() if self.date().isValid() else QtCore.QDate.currentDate()
        )
        cal.move(self.mapToGlobal(QtCore.QPoint(0, self.height())))
        cal.show()
        cal.raise_()
        cal.setFocus(QtCore.Qt.FocusReason.PopupFocusReason)

    def _hide_popup(self) -> None:
        self.calendarWidget().hide()

    def _setup_shortcuts(self) -> None:
        shortcuts = {
            "Ctrl+PgUp": lambda: self._step_months(-1),
            "Ctrl+PgDown": lambda: self._step_months(1),
            "Ctrl+Shift+PgUp": lambda: self._step_years(-1),
            "Ctrl+Shift+PgDown": lambda: self._step_years(1),
            "Ctrl+Left": lambda: self._select_delta_days(-1),
            "Ctrl+Right": lambda: self._select_delta_days(1),
            "Ctrl+Up": lambda: self._select_delta_days(-7),
            "Ctrl+Down": lambda: self._select_delta_days(7),
            "Ctrl+Home": self._select_today,
            "Ctrl+Space": self._toggle_popup,
            "Ctrl+Return": self._hide_popup,
            "Ctrl+End": self.erase,
        }
        for seq, handler in shortcuts.items():
            QtGui.QShortcut(QtGui.QKeySequence(seq), self, activated=handler)

    # endregion
