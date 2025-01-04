from __future__ import annotations

import datetime
import logging
from zoneinfo import ZoneInfo

import dateparser

from discord_reminder_bot import settings

logger: logging.Logger = logging.getLogger(__name__)


def parse_time(date_to_parse: str, timezone: str | None = None) -> datetime.datetime | None:
    """Parse a date string into a datetime object.

    Args:
        date_to_parse(str): The date string to parse.
        timezone(str, optional): The timezone to use. Defaults timezone from settings.

    Returns:
        datetime.datetime: The parsed datetime object.
    """
    logger.info("Parsing date: '%s' with timezone: '%s'", date_to_parse, timezone)

    if not date_to_parse:
        logger.error("No date provided to parse.")
        return None

    if not timezone:
        timezone = settings.config_timezone

    parsed_date: datetime.datetime | None = dateparser.parse(
        date_string=date_to_parse,
        settings={
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": f"{timezone}",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "RELATIVE_BASE": datetime.datetime.now(tz=ZoneInfo(timezone)),
        },
    )

    return parsed_date
