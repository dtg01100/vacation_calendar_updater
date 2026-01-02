from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from PySide6 import QtCore


# Define Settings locally to avoid circular import
@dataclass
class Settings:
    email_address: str
    calendar: str
    weekdays: Mapping[str, bool]
    send_email: bool = True


WEEKDAY_KEYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


@dataclass
class QtConfigManager:
    """Qt-based configuration manager using QSettings for better platform integration."""

    def __init__(self) -> None:
        self.settings = QtCore.QSettings(
            QtCore.QSettings.Format.IniFormat,
            QtCore.QSettings.Scope.UserScope,
            "VacationCalendarUpdater",
            "Settings",
        )

    def ensure_defaults(
        self,
        *,
        default_email: str,
        calendar_options: list[str],
    ) -> Settings:
        """Load settings, creating defaults if missing."""
        if not self.settings.contains("email_address"):
            self.settings.setValue("email_address", default_email)

        if not self.settings.contains("calendar") and calendar_options:
            self.settings.setValue("calendar", calendar_options[0])

        # Set default weekdays if not configured
        for key in WEEKDAY_KEYS:
            if not self.settings.contains(key):
                self.settings.setValue(key, True)

        # Set default email notification setting
        if not self.settings.contains("send_email"):
            self.settings.setValue("send_email", True)

        return self._load_settings()

    def save(self, settings: Settings) -> None:
        """Save settings using QSettings."""
        self.settings.setValue("email_address", settings.email_address)
        self.settings.setValue("calendar", settings.calendar)

        for key in WEEKDAY_KEYS:
            self.settings.setValue(key, bool(settings.weekdays.get(key, False)))

        self.settings.setValue("send_email", bool(settings.send_email))

    def _load_settings(self) -> Settings:
        """Load settings from QSettings."""
        weekdays = {}
        for key in WEEKDAY_KEYS:
            weekdays[key] = self.settings.value(key, defaultValue=True, type=bool)

        return Settings(
            email_address=self.settings.value(
                "email_address", defaultValue="", type=str
            ),
            calendar=self.settings.value("calendar", defaultValue="", type=str),
            weekdays=weekdays,
            send_email=self.settings.value("send_email", defaultValue=True, type=bool),
        )

    def get_undo_history_size(self) -> int:
        """Get the maximum undo history size setting."""
        return self.settings.value("undo_history_size", defaultValue=50, type=int)

    def set_undo_history_size(self, size: int) -> None:
        """Set the maximum undo history size."""
        self.settings.setValue("undo_history_size", size)

    def get_auto_save_undo(self) -> bool:
        """Get whether to auto-save undo history."""
        return self.settings.value("auto_save_undo", defaultValue=True, type=bool)

    def set_auto_save_undo(self, enabled: bool) -> None:
        """Set whether to auto-save undo history."""
        self.settings.setValue("auto_save_undo", enabled)

    def sync(self) -> None:
        """Force immediate sync of settings to disk."""
        self.settings.sync()
