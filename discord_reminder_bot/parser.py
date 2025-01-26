from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import dateparser
from loguru import logger

from discord_reminder_bot.settings import get_timezone


def parse_time(date_to_parse: str | None, timezone: str | None = None, use_dotenv: bool = True) -> datetime.datetime | None:  # noqa: FBT001, FBT002
    """Parse a date string into a datetime object.

    Args:
        date_to_parse(str): The date string to parse.
        timezone(str, optional): The timezone to use. Defaults timezone from settings.
        use_dotenv(bool, optional): Whether to load environment variables from a .env file. Defaults to True

    Returns:
        datetime.datetime: The parsed datetime object.
    """
    logger.info(f"Parsing date: '{date_to_parse}' with timezone: '{timezone}'")

    if not date_to_parse:
        logger.error("No date provided to parse.")
        return None

    if not timezone:
        timezone = get_timezone(use_dotenv)

    # Check if the timezone is valid
    try:
        tz = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ModuleNotFoundError):
        logger.error(f"Invalid timezone provided: '{timezone}'. Using {get_timezone(use_dotenv)} instead.")
        tz = ZoneInfo("UTC")

    try:
        parsed_date: datetime.datetime | None = dateparser.parse(
            date_string=date_to_parse,
            settings={
                "PREFER_DATES_FROM": "future",
                "TIMEZONE": f"{timezone}",
                "RETURN_AS_TIMEZONE_AWARE": True,
                "RELATIVE_BASE": datetime.datetime.now(tz=tz),
            },
        )
    except (ValueError, TypeError):
        return None

    logger.debug(f"Parsed date: {parsed_date} from '{date_to_parse}'")

    return parsed_date
