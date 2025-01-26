from __future__ import annotations

import pytest
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from discord_reminder_bot.settings import get_settings


def test_get_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_settings function with environment variables."""
    monkeypatch.setenv("SQLITE_LOCATION", "/test_jobs.sqlite")
    monkeypatch.setenv("TIMEZONE", "UTC")
    monkeypatch.setenv("BOT_TOKEN", "test_token")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("WEBHOOK_URL", "http://test_webhook_url")

    settings: dict[str, str | dict[str, SQLAlchemyJobStore] | dict[str, bool] | AsyncIOScheduler] = get_settings(use_dotenv=False)

    assert_msg = f"Expected /test_jobs.sqlite, got {settings['sqlite_location']}"
    assert settings["sqlite_location"] == "/test_jobs.sqlite", assert_msg

    assert_msg = f"Expected UTC, got {settings['config_timezone']}"
    assert settings["config_timezone"] == "UTC", assert_msg

    assert_msg = f"Expected test_token, got {settings['bot_token']}"
    assert settings["bot_token"] == "test_token", assert_msg  # noqa: S105

    assert_msg = f"Expected DEBUG, got {settings['log_level']}"
    assert settings["log_level"] == "DEBUG", assert_msg

    assert_msg = f"Expected http://test_webhook_url, got {settings['webhook_url']}"
    assert settings["webhook_url"] == "http://test_webhook_url", assert_msg

    assert_msg = f"Expected dict, got {type(settings['jobstores'])}"
    assert isinstance(settings["jobstores"], dict), assert_msg

    assert_msg: str = f"Expected SQLAlchemyJobStore, got {type(settings['jobstores']['default'])}"
    assert isinstance(settings["jobstores"]["default"], SQLAlchemyJobStore), assert_msg

    assert_msg = f"Expected AsyncIOScheduler, got {type(settings['scheduler'])}"
    assert isinstance(settings["scheduler"], AsyncIOScheduler), assert_msg


def test_get_settings_missing_bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_settings function with missing bot token."""
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    with pytest.raises(ValueError, match="Missing bot token"):
        get_settings(use_dotenv=False)


def test_get_settings_default_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_settings function with default values."""
    monkeypatch.delenv("SQLITE_LOCATION", raising=False)
    monkeypatch.delenv("TIMEZONE", raising=False)
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("WEBHOOK_URL", raising=False)
    monkeypatch.setenv("BOT_TOKEN", "default_token")
    monkeypatch.setenv("TIMEZONE", "UTC")

    settings: dict[str, str | dict[str, SQLAlchemyJobStore] | dict[str, bool] | AsyncIOScheduler] = get_settings(use_dotenv=False)

    assert_msg: str = f"Expected /jobs.sqlite, got {settings['sqlite_location']}"
    assert settings["sqlite_location"] == "/jobs.sqlite", assert_msg

    assert_msg = f"Expected UTC, got {settings['config_timezone']}"
    assert settings["config_timezone"] == "UTC", assert_msg

    assert_msg = f"Expected default_token, got {settings['bot_token']}"
    assert settings["bot_token"] == "default_token", assert_msg  # noqa: S105

    assert_msg = f"Expected INFO, got {settings['log_level']}"
    assert settings["log_level"] == "INFO", assert_msg

    assert_msg = f"Expected empty string, got {settings['webhook_url']}"
    assert not settings["webhook_url"], assert_msg

    assert_msg = f"Expected dict, got {type(settings['jobstores'])}"
    assert isinstance(settings["jobstores"], dict), assert_msg

    assert_msg = f"Expected SQLAlchemyJobStore, got {type(settings['jobstores']['default'])}"
    assert isinstance(settings["jobstores"]["default"], SQLAlchemyJobStore), assert_msg

    assert_msg = f"Expected AsyncIOScheduler, got {type(settings['scheduler'])}"
    assert isinstance(settings["scheduler"], AsyncIOScheduler), assert_msg
