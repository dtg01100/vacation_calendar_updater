from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import configparser
from typing import Iterable, Mapping
from PySide6 import QtCore

SETTINGS_SECTION = "settings"
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
class Settings:
    email_address: str
    calendar: str
    weekdays: Mapping[str, bool]
    send_email: bool = True

    def as_bool_list(self) -> list[bool]:
        return [bool(self.weekdays.get(key, False)) for key in WEEKDAY_KEYS]


class ConfigManager:
    """Configuration manager using Qt's QSettings for cross-platform support.
    
    Stores settings in platform-appropriate locations:
    - Linux: ~/.config/VacationCalendarUpdater/Settings.ini
    - macOS: ~/Library/Preferences/VacationCalendarUpdater.plist or .ini
    - Windows: Registry (HKEY_CURRENT_USER\\Software\\VacationCalendarUpdater) or AppData
    
    For testing, accepts an optional path parameter to use file-based storage.
    """
    
    def __init__(self, path: Path | None = None) -> None:
        # If a custom path is provided (for testing), use file-based storage
        if path:
            self.path = path
            self._is_file_based = True
        else:
            # Use Qt's QSettings for production
            self.path = None
            self._is_file_based = False
            self._qt_settings = QtCore.QSettings(
                QtCore.QSettings.Format.IniFormat,
                QtCore.QSettings.Scope.UserScope,
                "VacationCalendarUpdater",
                "Settings",
            )

    def ensure_defaults(
        self,
        *,
        default_email: str,
        calendar_options: Iterable[str],
    ) -> Settings:
        """Load settings, creating the config file with sane defaults if missing or invalid."""
        if self._is_file_based:
            return self._ensure_defaults_file(default_email, calendar_options)
        else:
            return self._ensure_defaults_qt(default_email, calendar_options)

    def _ensure_defaults_file(
        self, default_email: str, calendar_options: Iterable[str]
    ) -> Settings:
        """File-based implementation (for testing)."""
        calendar_options = list(calendar_options)
        config = self._read()

        if not config.has_section(SETTINGS_SECTION):
            config.add_section(SETTINGS_SECTION)

        needs_write = False

        if not config.has_option(SETTINGS_SECTION, "email_address"):
            config.set(SETTINGS_SECTION, "email_address", default_email)
            needs_write = True

        if not config.has_option(SETTINGS_SECTION, "calendar"):
            fallback_calendar = calendar_options[0] if calendar_options else ""
            config.set(SETTINGS_SECTION, "calendar", fallback_calendar)
            needs_write = True

        for key in WEEKDAY_KEYS:
            if not config.has_option(SETTINGS_SECTION, key):
                config.set(SETTINGS_SECTION, key, "True")
                needs_write = True

        if not config.has_option(SETTINGS_SECTION, "send_email"):
            config.set(SETTINGS_SECTION, "send_email", "True")
            needs_write = True

        if needs_write:
            self._write(config)

        settings = self._to_settings_file(config)

        # validate email + calendar now that defaults exist
        if not settings.email_address:
            settings.email_address = default_email
            needs_write = True

        if calendar_options and settings.calendar not in calendar_options:
            settings.calendar = calendar_options[0]
            needs_write = True

        if needs_write:
            self.save(settings)

        return settings

    def _ensure_defaults_qt(self, default_email: str, calendar_options: Iterable[str]) -> Settings:
        """Qt-based implementation (for production)."""
        calendar_options = list(calendar_options)
        
        if not self._qt_settings.contains("email_address"):
            self._qt_settings.setValue("email_address", default_email)

        if not self._qt_settings.contains("calendar") and calendar_options:
            self._qt_settings.setValue("calendar", calendar_options[0])

        for key in WEEKDAY_KEYS:
            if not self._qt_settings.contains(key):
                self._qt_settings.setValue(key, True)

        if not self._qt_settings.contains("send_email"):
            self._qt_settings.setValue("send_email", True)

        settings = self._load_settings_qt()

        # validate email + calendar
        needs_write = False
        if not settings.email_address:
            settings.email_address = default_email
            needs_write = True

        if calendar_options and settings.calendar not in calendar_options:
            settings.calendar = calendar_options[0]
            needs_write = True

        if needs_write:
            self.save(settings)

        return settings

    def save(self, settings: Settings) -> None:
        if self._is_file_based:
            self._save_file(settings)
        else:
            self._save_qt(settings)

    def _save_file(self, settings: Settings) -> None:
        """File-based save (for testing)."""
        config = configparser.RawConfigParser()
        config.add_section(SETTINGS_SECTION)
        config.set(SETTINGS_SECTION, "email_address", settings.email_address)
        config.set(SETTINGS_SECTION, "calendar", settings.calendar)
        for key in WEEKDAY_KEYS:
            config.set(SETTINGS_SECTION, key, str(bool(settings.weekdays.get(key, False))))
        config.set(SETTINGS_SECTION, "send_email", str(bool(settings.send_email)))
        self._write(config)

    def _save_qt(self, settings: Settings) -> None:
        """Qt-based save (for production)."""
        self._qt_settings.setValue("email_address", settings.email_address)
        self._qt_settings.setValue("calendar", settings.calendar)

        for key in WEEKDAY_KEYS:
            self._qt_settings.setValue(key, bool(settings.weekdays.get(key, False)))

        self._qt_settings.setValue("send_email", bool(settings.send_email))

    # File-based methods (for testing)
    def _read(self) -> configparser.RawConfigParser:
        config = configparser.RawConfigParser()
        if self.path.exists():
            config.read(self.path)
        return config

    def _write(self, config: configparser.RawConfigParser) -> None:
        if not self.path.parent.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w") as configfile:
            config.write(configfile)

    def _to_settings_file(self, config: configparser.RawConfigParser) -> Settings:
        section = SETTINGS_SECTION
        weekdays = {key: config.getboolean(section, key, fallback=True) for key in WEEKDAY_KEYS}
        return Settings(
            email_address=config.get(section, "email_address", fallback=""),
            calendar=config.get(section, "calendar", fallback=""),
            weekdays=weekdays,
            send_email=config.getboolean(section, "send_email", fallback=True),
        )

    def _load_settings_qt(self) -> Settings:
        """Load settings from Qt QSettings."""
        weekdays = {}
        for key in WEEKDAY_KEYS:
            weekdays[key] = self._qt_settings.value(key, defaultValue=True, type=bool)

        return Settings(
            email_address=self._qt_settings.value("email_address", defaultValue="", type=str),
            calendar=self._qt_settings.value("calendar", defaultValue="", type=str),
            weekdays=weekdays,
            send_email=self._qt_settings.value("send_email", defaultValue=True, type=bool),
        )
