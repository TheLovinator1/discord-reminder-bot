from __future__ import annotations

import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytz
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv


def get_settings(use_dotenv: bool = True) -> dict[str, str | dict[str, SQLAlchemyJobStore] | dict[str, bool] | AsyncIOScheduler]:  # noqa: FBT001, FBT002
    """Load environment variables and return the settings.

    Args:
        use_dotenv (bool, optional): Whether to load environment variables from a .env file. Defaults to True.

    Raises:
        ValueError: If the bot token is missing.

    Returns:
        dict: The settings.
    """
    if use_dotenv:
        load_dotenv(verbose=True)

    sqlite_location: str = os.getenv("SQLITE_LOCATION", default="/jobs.sqlite")
    log_level: str = os.getenv("LOG_LEVEL", default="INFO")
    webhook_url: str = os.getenv("WEBHOOK_URL", default="")

    bot_token: str = os.getenv("BOT_TOKEN", default="")
    if not bot_token:
        msg = "Missing bot token. Please set the BOT_TOKEN environment variable."
        raise ValueError(msg)

    config_timezone: str | None = os.getenv("TIMEZONE")
    if not config_timezone:
        msg = "Missing timezone. Please set the TIMEZONE environment variable."
        raise ValueError(msg)

    # Test if the timezone is valid
    try:
        ZoneInfo(config_timezone)
    except (ZoneInfoNotFoundError, ModuleNotFoundError) as e:
        msg: str = f"Invalid timezone: {config_timezone}. Error: {e}"
        raise ValueError(msg) from e

    jobstores: dict[str, SQLAlchemyJobStore] = {"default": SQLAlchemyJobStore(url=f"sqlite://{sqlite_location}")}
    job_defaults: dict[str, bool] = {"coalesce": True}
    scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        timezone=pytz.timezone(config_timezone),
        job_defaults=job_defaults,
    )
    return {
        "sqlite_location": sqlite_location,
        "config_timezone": config_timezone,
        "bot_token": bot_token,
        "log_level": log_level,
        "webhook_url": webhook_url,
        "jobstores": jobstores,
        "job_defaults": job_defaults,
        "scheduler": scheduler,
    }


def get_scheduler(use_dotenv: bool = True) -> AsyncIOScheduler:  # noqa: FBT001, FBT002
    """Return the scheduler instance.

    Args:
        use_dotenv (bool, optional): Whether to load environment variables from a .env file. Defaults to True

    Raises:
        TypeError: If the scheduler is not an instance of AsyncIOScheduler.
        KeyError: If the scheduler is missing from the settings.

    Returns:
        AsyncIOScheduler: The scheduler instance.
    """
    settings: dict[str, str | dict[str, SQLAlchemyJobStore] | dict[str, bool] | AsyncIOScheduler] = get_settings(use_dotenv)

    if scheduler := settings.get("scheduler"):
        if not isinstance(scheduler, AsyncIOScheduler):
            msg = "The scheduler is not an instance of AsyncIOScheduler."
            raise TypeError(msg)

        return scheduler

    msg = "The scheduler is missing from the settings."
    raise KeyError(msg)


def get_bot_token(use_dotenv: bool = True) -> str:  # noqa: FBT001, FBT002
    """Return the bot token.

    Args:
        use_dotenv (bool, optional): Whether to load environment variables from a .env file. Defaults to True

    Raises:
        TypeError: If the bot token is not a string.
        KeyError: If the bot token is missing from the settings.

    Returns:
        str: The bot token.
    """
    settings: dict[str, str | dict[str, SQLAlchemyJobStore] | dict[str, bool] | AsyncIOScheduler] = get_settings(use_dotenv)

    if bot_token := settings.get("bot_token"):
        if not isinstance(bot_token, str):
            msg = "The bot token is not a string."
            raise TypeError(msg)

        return bot_token

    msg = "The bot token is missing from the settings."
    raise KeyError(msg)


def get_webhook_url(use_dotenv: bool = True) -> str:  # noqa: FBT001, FBT002
    """Return the webhook URL.

    Args:
        use_dotenv (bool, optional): Whether to load environment variables from a .env file. Defaults to True

    Raises:
        TypeError: If the webhook URL is not a string.
        KeyError: If the webhook URL is missing from the settings.

    Returns:
        str: The webhook URL.
    """
    settings: dict[str, str | dict[str, SQLAlchemyJobStore] | dict[str, bool] | AsyncIOScheduler] = get_settings(use_dotenv)

    if webhook_url := settings.get("webhook_url"):
        if not isinstance(webhook_url, str):
            msg = "The webhook URL is not a string."
            raise TypeError(msg)

        return webhook_url

    msg = "The webhook URL is missing from the settings."
    raise KeyError(msg)
