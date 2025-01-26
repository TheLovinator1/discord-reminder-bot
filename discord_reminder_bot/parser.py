from __future__ import annotations

import datetime
import os
from zoneinfo import ZoneInfo

import dateparser
from loguru import logger


def parse_time(date_to_parse: str | None, timezone: str | None = os.getenv("TIMEZONE")) -> datetime.datetime | None:
    """Parse a date string into a datetime object.

    Args:
        date_to_parse(str): The date string to parse.
        timezone(str, optional): The timezone to use. Defaults timezone from settings.

    Returns:
        datetime.datetime: The parsed datetime object.
    """
    if not date_to_parse:
        logger.error("No date provided to parse.")
        return None

    if not timezone:
        logger.error("No timezone provided to parse date.")
        return None

    logger.info(f"Parsing date: '{date_to_parse}' with timezone: '{timezone}'")

    try:
        parsed_date: datetime.datetime | None = dateparser.parse(
            date_string=date_to_parse,
            settings={
                "PREFER_DATES_FROM": "future",
                "TIMEZONE": f"{timezone}",
                "RETURN_AS_TIMEZONE_AWARE": True,
                "RELATIVE_BASE": datetime.datetime.now(tz=ZoneInfo(str(timezone))),
            },
        )
    except (ValueError, TypeError) as e:
        logger.error(f"Failed to parse date: '{date_to_parse}' with timezone: '{timezone}'. Error: {e}")
        return None

    logger.debug(f"Parsed date: {parsed_date} from '{date_to_parse}'")

    return parsed_date
