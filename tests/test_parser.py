from __future__ import annotations

import zoneinfo
from typing import TYPE_CHECKING

import pytest

from discord_reminder_bot.parser import parse_time

if TYPE_CHECKING:
    from datetime import datetime


def test_parse_time_valid_date_and_timezone() -> None:
    """Test the `parse_time` function to ensure it correctly parses a date string into a datetime object."""
    date_to_parse = "2023-10-10 10:00:00"
    timezone = "UTC"
    result: datetime | None = parse_time(date_to_parse, timezone)
    assert result is not None
    assert result.tzinfo is not None
    assert result.strftime("%Y-%m-%d %H:%M:%S") == "2023-10-10 10:00:00"


def test_parse_time_no_date() -> None:
    """Test the `parse_time` function to ensure it correctly handles no date provided."""
    date_to_parse = None
    timezone = "UTC"
    result: datetime | None = parse_time(date_to_parse, timezone)
    assert result is None


def test_parse_time_no_timezone() -> None:
    """Test the `parse_time` function to ensure it correctly handles no timezone provided."""
    date_to_parse = "2023-10-10 10:00:00"
    timezone = None
    result: datetime | None = parse_time(date_to_parse, timezone)
    assert result is None


def test_parse_time_invalid_date() -> None:
    """Test the `parse_time` function to ensure it correctly handles an invalid date string."""
    date_to_parse = "invalid date"
    timezone = "UTC"
    result: datetime | None = parse_time(date_to_parse, timezone)
    assert result is None


def test_parse_time_invalid_timezone() -> None:
    """Test the `parse_time` function to ensure it correctly handles an invalid timezone."""
    date_to_parse = "2023-10-10 10:00:00"
    timezone = "Invalid/Timezone"
    with pytest.raises(zoneinfo.ZoneInfoNotFoundError):
        parse_time(date_to_parse, timezone)


def test_parse_time_with_env_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the `parse_time` function to ensure it correctly parses a date string into a datetime object using the timezone from the environment."""  # noqa: E501
    date_to_parse = "2023-10-10 10:00:00"
    result: datetime | None = parse_time(date_to_parse, "UTC")

    assert_msg: str = "Expected datetime object, got None"
    assert result is not None, assert_msg

    assert_msg = "Expected timezone-aware datetime object, got naive datetime object"
    assert result.tzinfo is not None, assert_msg

    assert_msg = f"Expected 2023-10-10 10:00:00, got {result.strftime('%Y-%m-%d %H:%M:%S')}"
    assert result.strftime("%Y-%m-%d %H:%M:%S") == "2023-10-10 10:00:00", assert_msg
