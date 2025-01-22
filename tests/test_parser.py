from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from discord_reminder_bot import settings
from discord_reminder_bot.parser import parse_time


def test_parse_time_valid_date() -> None:
    """Test the `parse_time` function with a valid date string."""
    date_to_parse = "tomorrow at 5pm"
    timezone = "UTC"
    result: datetime.datetime | None = parse_time(date_to_parse, timezone, use_dotenv=False)
    assert result is not None
    assert result.tzinfo == ZoneInfo(timezone)


def test_parse_time_no_date() -> None:
    """Test the `parse_time` function with no date string."""
    date_to_parse: str = ""
    timezone = "UTC"
    result: datetime.datetime | None = parse_time(date_to_parse, timezone, use_dotenv=False)
    assert result is None


def test_parse_time_no_timezone() -> None:
    """Test the `parse_time` function with no timezone."""
    date_to_parse = "tomorrow at 5pm"
    result: datetime.datetime | None = parse_time(date_to_parse, use_dotenv=False)
    assert result is not None
    assert result.tzinfo == ZoneInfo(settings.get_timezone(use_dotenv=False))


def test_parse_time_invalid_date() -> None:
    """Test the `parse_time` function with an invalid date string."""
    date_to_parse = "invalid date"
    timezone = "UTC"
    result: datetime.datetime | None = parse_time(date_to_parse, timezone, use_dotenv=False)
    assert result is None


@freeze_time("2023-01-01 12:00:00")
def test_parse_time_invalid_timezone() -> None:
    """Test the `parse_time` function with an invalid timezone."""
    date_to_parse = "tomorrow at 5pm"
    timezone = "Invalid/Timezone"
    result: datetime.datetime | None = parse_time(date_to_parse, timezone, use_dotenv=False)
    assert result is not None
    assert result.tzinfo == ZoneInfo("UTC")
    assert result == datetime.datetime(2023, 1, 2, 17, 0, tzinfo=ZoneInfo("UTC"))
