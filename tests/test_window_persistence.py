"""Test that email address and calendar selection persist across window close/reopen."""

from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
from PySide6 import QtGui, QtCore

from app.config import ConfigManager, Settings


def test_save_settings_to_disk_persists_email_and_calendar(tmp_path):
    """Test that _save_settings_to_disk properly saves email and calendar to disk."""
    cfg_path = tmp_path / "settings.cfg"
    
    # Create initial config
    config_manager = ConfigManager(path=cfg_path)
    config_manager.save(Settings(
        email_address="old@example.com",
        calendar="OldCalendar",
        weekdays={"monday": True, "tuesday": False, "wednesday": True, "thursday": False, "friday": True, "saturday": False, "sunday": False},
        send_email=True,
    ))
    
    # Verify old values were saved
    loaded = config_manager.ensure_defaults(default_email="", calendar_options=["OldCalendar", "NewCalendar"])
    assert loaded.email_address == "old@example.com"
    assert loaded.calendar == "OldCalendar"
    
    # Now simulate what happens when user changes email and calendar, then closes window
    # by creating a new Settings object with different values
    new_settings = Settings(
        email_address="new@example.com",
        calendar="NewCalendar",
        weekdays={"monday": True, "tuesday": True, "wednesday": True, "thursday": True, "friday": True, "saturday": False, "sunday": False},
        send_email=False,
    )
    config_manager.save(new_settings)
    
    # Verify new values persisted to disk
    config_manager2 = ConfigManager(path=cfg_path)
    loaded2 = config_manager2.ensure_defaults(default_email="", calendar_options=["OldCalendar", "NewCalendar"])
    assert loaded2.email_address == "new@example.com"
    assert loaded2.calendar == "NewCalendar"
    assert loaded2.send_email is False


def test_config_persistence_roundtrip_multiple_times(tmp_path):
    """Test that config values persist correctly across multiple save/load cycles."""
    cfg_path = tmp_path / "settings.cfg"
    
    test_cases = [
        ("user1@example.com", "Primary"),
        ("user2@example.com", "Work"),
        ("user3@example.com", "Personal"),
    ]
    
    for email, calendar in test_cases:
        config_manager = ConfigManager(path=cfg_path)
        settings = Settings(
            email_address=email,
            calendar=calendar,
            weekdays={"monday": True, "tuesday": True, "wednesday": True, "thursday": True, "friday": True, "saturday": False, "sunday": False},
            send_email=True,
        )
        config_manager.save(settings)
        
        # Reload and verify
        loaded = config_manager.ensure_defaults(
            default_email="",
            calendar_options=["Primary", "Work", "Personal"]
        )
        assert loaded.email_address == email, f"Expected {email}, got {loaded.email_address}"
        assert loaded.calendar == calendar, f"Expected {calendar}, got {loaded.calendar}"
