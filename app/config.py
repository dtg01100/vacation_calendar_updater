from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import configparser
from typing import Iterable, Mapping

CONFIG_PATH = Path.home() / ".vacation_calendar_updater.cfg"
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
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or CONFIG_PATH

    def ensure_defaults(
        self,
        *,
        default_email: str,
        calendar_options: Iterable[str],
    ) -> Settings:
        """Load settings, creating the config file with sane defaults if missing or invalid."""
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

        settings = self._to_settings(config)

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

    def save(self, settings: Settings) -> None:
        config = configparser.RawConfigParser()
        config.add_section(SETTINGS_SECTION)
        config.set(SETTINGS_SECTION, "email_address", settings.email_address)
        config.set(SETTINGS_SECTION, "calendar", settings.calendar)
        for key in WEEKDAY_KEYS:
            config.set(SETTINGS_SECTION, key, str(bool(settings.weekdays.get(key, False))))
        config.set(SETTINGS_SECTION, "send_email", str(bool(settings.send_email)))
        self._write(config)

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

    def _to_settings(self, config: configparser.RawConfigParser) -> Settings:
        section = SETTINGS_SECTION
        weekdays = {key: config.getboolean(section, key, fallback=True) for key in WEEKDAY_KEYS}
        return Settings(
            email_address=config.get(section, "email_address", fallback=""),
            calendar=config.get(section, "calendar", fallback=""),
            weekdays=weekdays,
            send_email=config.getboolean(section, "send_email", fallback=True),
        )
