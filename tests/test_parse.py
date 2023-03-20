from datetime import datetime

import tzlocal

from discord_reminder_bot.parse import ParsedTime, parse_time


def test_parse_time() -> None:
    """Test the parse_time function."""
    parsed_time: ParsedTime = parse_time("18 January 2040")
    assert parsed_time.err is False
    assert not parsed_time.err_msg
    assert parsed_time.date_to_parse == "18 January 2040"
    assert parsed_time.parsed_time
    assert parsed_time.parsed_time.strftime("%Y-%m-%d %H:%M:%S") == "2040-01-18 00:00:00"

    parsed_time: ParsedTime = parse_time("18 January 2040 12:00")
    assert parsed_time.err is False
    assert not parsed_time.err_msg
    assert parsed_time.date_to_parse == "18 January 2040 12:00"
    assert parsed_time.parsed_time
    assert parsed_time.parsed_time.strftime("%Y-%m-%d %H:%M:%S") == "2040-01-18 12:00:00"

    parsed_time: ParsedTime = parse_time("18 January 2040 12:00:00")
    assert parsed_time.err is False
    assert not parsed_time.err_msg
    assert parsed_time.date_to_parse == "18 January 2040 12:00:00"
    assert parsed_time.parsed_time
    assert parsed_time.parsed_time.strftime("%Y-%m-%d %H:%M:%S") == "2040-01-18 12:00:00"

    parsed_time: ParsedTime = parse_time("18 January 2040 12:00:00 UTC")
    assert parsed_time.err is False
    assert not parsed_time.err_msg
    assert parsed_time.date_to_parse == "18 January 2040 12:00:00 UTC"
    assert parsed_time.parsed_time
    assert parsed_time.parsed_time.strftime("%Y-%m-%d %H:%M:%S") == "2040-01-18 13:00:00"

    parsed_time: ParsedTime = parse_time("18 January 2040 12:00:00 Europe/Stockholm")
    assert parsed_time.err is True
    assert parsed_time.err_msg == "Could not parse the date."
    assert parsed_time.date_to_parse == "18 January 2040 12:00:00 Europe/Stockholm"
    assert parsed_time.parsed_time is None


def test_ParsedTime() -> None:  # noqa: N802
    """Test the ParsedTime class."""
    parsed_time: ParsedTime = ParsedTime(
        err=False,
        err_msg="",
        date_to_parse="18 January 2040",
        parsed_time=datetime(2040, 1, 18, 0, 0, 0, tzinfo=tzlocal.get_localzone()),
    )
    assert parsed_time.err is False
    assert not parsed_time.err_msg
    assert parsed_time.date_to_parse == "18 January 2040"
    assert parsed_time.parsed_time
    assert parsed_time.parsed_time.strftime("%Y-%m-%d %H:%M:%S") == "2040-01-18 00:00:00"

    parsed_time: ParsedTime = ParsedTime(
        err=True,
        err_msg="Could not parse the date.",
        date_to_parse="18 January 2040 12:00:00 Europe/Stockholm",
        parsed_time=None,
    )
    assert parsed_time.err is True
    assert parsed_time.err_msg == "Could not parse the date."
    assert parsed_time.date_to_parse == "18 January 2040 12:00:00 Europe/Stockholm"
    assert parsed_time.parsed_time is None
