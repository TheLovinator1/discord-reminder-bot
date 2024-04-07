from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import dateparser
import pytz

from discord_reminder_bot.settings import config_timezone

if TYPE_CHECKING:
    from datetime import datetime


# TODO(TheLovinator): Add tests for this function  # noqa: TD003
# TODO(TheLovinator): Add dateparser DATE_ORDER to settings  # noqa: TD003
# TODO(TheLovinator): Add PREFER_DAY_OF_MONTH to settings  # noqa: TD003
# TODO(TheLovinator): Add PREFER_MONTH_OF_YEAR to settings  # noqa: TD003


@dataclass
class ParsedTime:
    """A dataclass for the parsed time."""

    parsed: datetime | None
    timezone: str
    original: str
    error: str | None


def parse_time(date_to_parse: str, timezone: str | None) -> None | ParsedTime:
    """Parse the datetime from a string.

    Args:
        date_to_parse: The date or time to parse.
        timezone: Time zone for date/time calculations. For example: 'Europe/Stockholm'.

    Raises:
        UnknownTimeZoneError: If the timezone is not a valid timezone.

    Returns:
        ParsedTime: The parsed time, timezone, original string, and error.
    """
    our_timezone: str = timezone or config_timezone

    # Raise an exception if the timezone is invalid
    try:
        pytz.timezone(our_timezone)
    except pytz.UnknownTimeZoneError as e:
        return ParsedTime(
            parsed=None,
            timezone=our_timezone,
            original=date_to_parse,
            error=f"Unknown timezone: {e}.",
        )

    parsed: datetime | None = dateparser.parse(
        date_string=date_to_parse or "now",
        settings={
            "TIMEZONE": our_timezone,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "CACHE_SIZE_LIMIT": 0,
            "PREFER_DATES_FROM": "future",
        },  # type: ignore  # noqa: PGH003
    )

    return ParsedTime(
        parsed=parsed,
        timezone=our_timezone,
        original=date_to_parse,
        error=None,
    )
