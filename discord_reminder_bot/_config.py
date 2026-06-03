from __future__ import annotations

import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytz
from loguru import logger

SCHEDULER_TIMEZONE: pytz.BaseTzInfo | None = None


def get_scheduler_timezone() -> pytz.BaseTzInfo:
    """Load (once) and return the configured timezone.

    The timezone is read from the ``TIMEZONE`` environment variable on first
    call and then cached.  This lazy-loading approach allows test fixtures to
    set ``TIMEZONE`` before any code imports this module.

    Returns:
        A valid pytz timezone instance.

    Raises:
        ValueError: If the ``TIMEZONE`` env var is missing or invalid.
    """
    global SCHEDULER_TIMEZONE  # noqa: PLW0603
    if SCHEDULER_TIMEZONE is not None:
        return SCHEDULER_TIMEZONE

    config_timezone: str | None = os.getenv("TIMEZONE")
    if not config_timezone:
        msg = "Missing timezone. Please set the TIMEZONE environment variable."
        raise ValueError(msg)

    # Validate the timezone string
    try:
        ZoneInfo(config_timezone)
    except (ZoneInfoNotFoundError, ModuleNotFoundError) as e:
        msg = f"Invalid timezone: {config_timezone}. Error: {e}"
        raise ValueError(msg) from e

    logger.info(f"Using timezone: {config_timezone}. If this is incorrect, please set the TIMEZONE environment variable.")
    SCHEDULER_TIMEZONE = pytz.timezone(config_timezone)
    return SCHEDULER_TIMEZONE
