from __future__ import annotations

import configparser
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from PySide6 import QtCore

SETTINGS_SECTION = "settings"


def get_config_directory() -> Path:
    """Get platform-appropriate config directory using Qt's standard paths.

    Returns:
        Path: The configuration directory for the application.
    """
    config_dir = QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.StandardLocation.ConfigLocation
    )
    return Path(config_dir)


WEEKDAY_KEYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

DEFAULT_TIME_PRESETS = ["08:00", "09:00", "12:00", "13:00", "14:00", "17:00"]
DEFAULT_START_TIME = "08:00"
DEFAULT_DAY_LENGTH = "08:00"


@dataclass
class Settings:
    email_address: str
    calendar: str
    weekdays: Mapping[str, bool]
    send_email: bool = True
    time_presets: list[str] | None = None  # e.g., ["08:00", "09:00", "12:00", "13:00", "14:00", "17:00"]
    last_start_time: str = DEFAULT_START_TIME  # HH:MM format
    last_day_length: str = DEFAULT_DAY_LENGTH  # HH:MM format

    def __post_init__(self) -> None:
        """Initialize default time presets if not provided."""
        if self.time_presets is None:
            self.time_presets = DEFAULT_TIME_PRESETS

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
        return self._ensure_defaults_qt(default_email, calendar_options)

    def _validate_and_save_settings(
        self, settings: Settings, default_email: str, calendar_options: list[str]
    ) -> Settings:
        """Validate settings and save if changes are needed."""
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

        return self._validate_and_save_settings(settings, default_email, calendar_options)

    def _ensure_defaults_qt(
        self, default_email: str, calendar_options: Iterable[str]
    ) -> Settings:
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

        return self._validate_and_save_settings(settings, default_email, calendar_options)

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
            config.set(
                SETTINGS_SECTION, key, str(bool(settings.weekdays.get(key, False)))
            )
        config.set(SETTINGS_SECTION, "send_email", str(bool(settings.send_email)))
        # Save time presets as comma-separated string
        if settings.time_presets:
            config.set(SETTINGS_SECTION, "time_presets", ",".join(settings.time_presets))
        # Save last used times
        config.set(SETTINGS_SECTION, "last_start_time", settings.last_start_time)
        config.set(SETTINGS_SECTION, "last_day_length", settings.last_day_length)
        self._write(config)

    def _save_qt(self, settings: Settings) -> None:
        """Qt-based save (for production)."""
        self._qt_settings.setValue("email_address", settings.email_address)
        self._qt_settings.setValue("calendar", settings.calendar)

        for key in WEEKDAY_KEYS:
            self._qt_settings.setValue(key, bool(settings.weekdays.get(key, False)))

        self._qt_settings.setValue("send_email", bool(settings.send_email))

        # Save time presets as comma-separated string
        if settings.time_presets:
            self._qt_settings.setValue("time_presets", ",".join(settings.time_presets))

        # Save last used times
        self._qt_settings.setValue("last_start_time", settings.last_start_time)
        self._qt_settings.setValue("last_day_length", settings.last_day_length)

    # File-based methods (for testing)
    def _read(self) -> configparser.RawConfigParser:
        config = configparser.RawConfigParser()
        if self.path and self.path.exists():
            config.read(self.path)
        return config

    def _write(self, config: configparser.RawConfigParser) -> None:
        if self.path:
            if not self.path.parent.exists():
                self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w") as configfile:
                config.write(configfile)

    def _to_settings_file(self, config: configparser.RawConfigParser) -> Settings:
        section = SETTINGS_SECTION
        weekdays = {
            key: config.getboolean(section, key, fallback=True) for key in WEEKDAY_KEYS
        }

        # Load time presets from comma-separated string
        time_presets_str = config.get(section, "time_presets", fallback=",".join(DEFAULT_TIME_PRESETS))
        time_presets = [t.strip() for t in time_presets_str.split(",") if t.strip()]

        return Settings(
            email_address=config.get(section, "email_address", fallback=""),
            calendar=config.get(section, "calendar", fallback=""),
            weekdays=weekdays,
            send_email=config.getboolean(section, "send_email", fallback=True),
            time_presets=time_presets,
            last_start_time=config.get(section, "last_start_time", fallback=DEFAULT_START_TIME),
            last_day_length=config.get(section, "last_day_length", fallback=DEFAULT_DAY_LENGTH),
        )

    def _load_settings_qt(self) -> Settings:
        """Load settings from Qt QSettings."""
        weekdays = {}
        for key in WEEKDAY_KEYS:
            value = self._qt_settings.value(key, defaultValue=True)
            weekdays[key] = bool(value) if value is not None else True

        # Load time presets from comma-separated string
        time_presets_str = self._qt_settings.value(
            "time_presets",
            defaultValue=",".join(DEFAULT_TIME_PRESETS)
        )
        if isinstance(time_presets_str, str):
            time_presets = [t.strip() for t in time_presets_str.split(",") if t.strip()]
        else:
            time_presets = DEFAULT_TIME_PRESETS

        email_address = self._qt_settings.value("email_address", defaultValue="")
        calendar = self._qt_settings.value("calendar", defaultValue="")
        send_email = self._qt_settings.value("send_email", defaultValue=True)
        last_start_time = self._qt_settings.value("last_start_time", defaultValue=DEFAULT_START_TIME)
        last_day_length = self._qt_settings.value("last_day_length", defaultValue=DEFAULT_DAY_LENGTH)

        return Settings(
            email_address=str(email_address) if email_address is not None else "",
            calendar=str(calendar) if calendar is not None else "",
            weekdays=weekdays,
            send_email=bool(send_email) if send_email is not None else True,
            time_presets=time_presets,
            last_start_time=str(last_start_time) if last_start_time is not None else "08:00",
            last_day_length=str(last_day_length) if last_day_length is not None else "08:00",
        )
