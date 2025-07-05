from __future__ import annotations

import os
import platform
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytz
import sentry_sdk
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from loguru import logger

load_dotenv(verbose=True)

default_sentry_dsn: str = "https://c4c61a52838be9b5042144420fba5aaa@o4505228040339456.ingest.us.sentry.io/4508707268984832"
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN", default_sentry_dsn),
    environment=platform.node() or "Unknown",
    traces_sample_rate=1.0,
    send_default_pii=True,
)


def get_scheduler() -> AsyncIOScheduler:
    """Return the scheduler instance.

    Uses the SQLITE_LOCATION environment variable for the SQLite database location.

    Raises:
        ValueError: If the timezone is missing or invalid.

    Returns:
        AsyncIOScheduler: The scheduler instance.
    """
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

    logger.info(f"Using timezone: {config_timezone}. If this is incorrect, please set the TIMEZONE environment variable.")

    sqlite_location: str = os.getenv("SQLITE_LOCATION", default="/jobs.sqlite")
    logger.info(f"Using SQLite database at: {sqlite_location}")

    jobstores: dict[str, SQLAlchemyJobStore] = {"default": SQLAlchemyJobStore(url=f"sqlite://{sqlite_location}")}
    job_defaults: dict[str, bool] = {"coalesce": True}
    timezone = pytz.timezone(config_timezone)
    return AsyncIOScheduler(jobstores=jobstores, timezone=timezone, job_defaults=job_defaults)


scheduler: AsyncIOScheduler = get_scheduler()
