from __future__ import annotations

import os

import pytz
from dotenv import find_dotenv, load_dotenv
from loguru import logger

load_dotenv(dotenv_path=find_dotenv(), verbose=True)

log_level: str = os.getenv(key="LOG_LEVEL", default="INFO")

# Discord webhook url for error messages
webhook_url: str = os.getenv(key="WEBHOOK_URL", default="")
if not webhook_url:
    logger.warning(
        "No webhook url configured. You will not receive any error messages.",
    )

# Get the bot token from the environment or raise an exception
bot_token: str = os.getenv(key="BOT_TOKEN", default="")
if not bot_token:
    err_msg = "Missing bot token. Please set the BOT_TOKEN environment variable or add it to .env."  # noqa: E501
    raise ValueError(err_msg)


# Get the timezone from the environment or use UTC as default
try:
    config_timezone: str = os.getenv(key="TIMEZONE", default="UTC")
    if not config_timezone:
        msg = "Missing timezone. Please set the TIMEZONE environment variable or add it to .env."  # noqa: E501
        raise ValueError(msg)

    logger.info(f"Using timezone: {config_timezone}")
    scheduler_timezone = pytz.timezone(config_timezone)
    logger.debug(f"Timezone converted to: {scheduler_timezone}")
except pytz.exceptions.UnknownTimeZoneError as e:
    err_msg: str = f"Invalid timezone: {config_timezone}. Please set a valid timezone in the TIMEZONE environment variable or add it to .env."  # noqa: E501
    raise ValueError(err_msg) from e
