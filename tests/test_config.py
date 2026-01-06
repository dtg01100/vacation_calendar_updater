from app.config import ConfigManager, Settings


def test_config_defaults_created(tmp_path):
    cfg_path = tmp_path / "settings.cfg"
    manager = ConfigManager(path=cfg_path)
    settings = manager.ensure_defaults(
        default_email="user@example.com", calendar_options=["cal1", "cal2"]
    )
    assert settings.email_address == "user@example.com"
    assert settings.calendar == "cal1"
    assert settings.send_email is True
    # persisted
    loaded = ConfigManager(path=cfg_path).ensure_defaults(
        default_email="user@example.com", calendar_options=["cal1"]
    )
    assert loaded.calendar == "cal1"


def test_config_save_roundtrip(tmp_path):
    cfg_path = tmp_path / "settings.cfg"
    manager = ConfigManager(path=cfg_path)
    settings = Settings(
        email_address="person@example.com",
        calendar="cal2",
        weekdays={
            "monday": False,
            "tuesday": True,
            "wednesday": False,
            "thursday": True,
            "friday": False,
            "saturday": False,
            "sunday": False,
        },
        send_email=False,
    )
    manager.save(settings)
    loaded = manager.ensure_defaults(
        default_email="x@example.com", calendar_options=["cal2"]
    )
    assert loaded.email_address == "person@example.com"
    assert loaded.calendar == "cal2"
    assert loaded.weekdays["tuesday"] is True
    assert loaded.send_email is False
