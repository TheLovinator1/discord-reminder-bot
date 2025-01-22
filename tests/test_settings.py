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

    assert settings["sqlite_location"] == "/test_jobs.sqlite"
    assert settings["config_timezone"] == "UTC"
    assert settings["bot_token"] == "test_token"  # noqa: S105
    assert settings["log_level"] == "DEBUG"
    assert settings["webhook_url"] == "http://test_webhook_url"
    assert isinstance(settings["jobstores"]["default"], SQLAlchemyJobStore)  # type: ignore  # noqa: PGH003


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

    settings: dict[str, str | dict[str, SQLAlchemyJobStore] | dict[str, bool] | AsyncIOScheduler] = get_settings(use_dotenv=False)

    assert settings["sqlite_location"] == "/jobs.sqlite"
    assert settings["config_timezone"] == "UTC"
    assert settings["bot_token"] == "default_token"  # noqa: S105
    assert settings["log_level"] == "INFO"
    assert not settings["webhook_url"]
    assert isinstance(settings["jobstores"]["default"], SQLAlchemyJobStore)  # type: ignore  # noqa: PGH003
    assert isinstance(settings["scheduler"], AsyncIOScheduler)
