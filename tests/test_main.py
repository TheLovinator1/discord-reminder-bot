from __future__ import annotations

import zoneinfo
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from discord_reminder_bot import main
from discord_reminder_bot.helpers import calculate, parse_time
from discord_reminder_bot.main import _format_late_notice

if TYPE_CHECKING:
    from apscheduler.job import Job


def dummy_job() -> None:
    """Dummy job function for testing."""


def test_calculate() -> None:
    """Test the calculate function with various job inputs."""
    scheduler = BackgroundScheduler()
    scheduler.timezone = UTC
    scheduler.start()

    # Create a job with a DateTrigger
    run_date = datetime(2270, 10, 1, 12, 0, 0, tzinfo=scheduler.timezone)
    job: Job = scheduler.add_job(dummy_job, trigger=DateTrigger(run_date=run_date), id="test_job", name="Test Job")

    expected_output = "<t:9490737600:R>"
    assert_msg: str = f"Expected {expected_output}, got {calculate(job)}\nState:{job.__getstate__()}"
    assert calculate(job) == expected_output, assert_msg

    # Modify the job to have a next_run_time
    job.modify(next_run_time=run_date)
    assert_msg: str = f"Expected {expected_output}, got {calculate(job)}\nState:{job.__getstate__()}"
    assert calculate(job) == expected_output, assert_msg

    # Paused job should return "Paused"
    job.pause()
    assert_msg: str = f"Expected 'Paused', got {calculate(job)}\nState:{job.__getstate__()}"
    assert calculate(job) == "Paused", assert_msg

    scheduler.shutdown()


def test_calculate_cronjob() -> None:
    """Test the calculate function with a CronTrigger job."""
    scheduler = BackgroundScheduler()
    scheduler.start()

    run_date = datetime(2270, 10, 1, 12, 0, 0, tzinfo=scheduler.timezone)
    job: Job = scheduler.add_job(
        dummy_job,
        trigger=CronTrigger(
            second=run_date.second,
            minute=run_date.minute,
            hour=run_date.hour,
            day=run_date.day,
            month=run_date.month,
            year=run_date.year,
        ),
    )
    # Force next_run_time to expected value for testing
    job.modify(next_run_time=run_date)

    expected_output: str = f"<t:{int(run_date.timestamp())}:R>"
    assert calculate(job) == expected_output, f"Expected {expected_output}, got {calculate(job)}\nState:{job.__getstate__()}"

    job.pause()
    assert calculate(job) == "Paused", f"Expected Paused, got {calculate(job)}\nState:{job.__getstate__()}"
    scheduler.shutdown()


def test_calculate_intervaljob() -> None:
    """Test the calculate function with an IntervalTrigger job."""
    scheduler = BackgroundScheduler()
    scheduler.start()

    run_date = datetime(2270, 12, 31, 23, 59, 59, tzinfo=scheduler.timezone)
    job = scheduler.add_job(dummy_job, trigger=IntervalTrigger(seconds=3600), id="test_interval_job", name="Test Interval Job")
    # Force next_run_time to expected value for testing
    job.modify(next_run_time=run_date)

    expected_output = f"<t:{int(run_date.timestamp())}:R>"
    assert calculate(job) == expected_output, f"Expected {expected_output}, got {calculate(job)}\nState:{job.__getstate__()}"

    # Paused job should return "Paused"
    job.pause()
    assert calculate(job) == "Paused", f"Expected Paused, got {calculate(job)}\nState:{job.__getstate__()}"
    scheduler.shutdown()


def test_format_late_notice_none() -> None:
    """None should return an empty string."""
    assert not _format_late_notice(None)


def test_format_late_notice_on_time() -> None:
    """A recent scheduled time (within 60 s) should return an empty string."""
    recent = datetime.now(tz=UTC).isoformat()
    assert not _format_late_notice(recent)


def test_format_late_notice_late() -> None:
    """A time well in the past should return a late-notice string."""
    past = datetime(2024, 1, 1, tzinfo=UTC).isoformat()
    result = _format_late_notice(past)
    assert "Ran late!" in result
    assert f"<t:{int(datetime(2024, 1, 1, tzinfo=UTC).timestamp())}:R>" in result


def test_format_late_notice_invalid() -> None:
    """An unparsable string should return an empty string (no crash)."""
    assert not _format_late_notice("not-a-date")


def test_if_send_to_discord_is_in_main() -> None:
    """send_to_discords needs to be in main for this program to work."""
    assert_msg: str = f"send_to_discord is not in main. Current functions in main: {dir(main)}"
    assert hasattr(main, "send_to_discord"), assert_msg


def test_if_send_to_user_is_in_main() -> None:
    """send_to_user needs to be in main for this program to work."""
    assert_msg: str = f"send_to_user is not in main. Current functions in main: {dir(main)}"
    assert hasattr(main, "send_to_user"), assert_msg


def test_send_to_discord_accepts_old_kwargs_without_scheduled_time() -> None:
    """Verify send_to_discord can be called with old kwargs that lack _scheduled_time.

    Old reminders persisted in the APScheduler SQLite database before _scheduled_time
    was added have kwargs like: {channel_id, message, author_id} — without
    _scheduled_time. When APScheduler fires those jobs, it calls
    send_to_discord(**kwargs), which must work because _scheduled_time has a
    default value of None.
    """
    import inspect

    sig = inspect.signature(main.send_to_discord)
    assert_msg = "send_to_discord signature does not have _scheduled_time=None as a keyword argument"
    assert "_scheduled_time" in sig.parameters, assert_msg
    param = sig.parameters["_scheduled_time"]
    assert param.default is None, f"Expected _scheduled_time default to be None, got {param.default}"

    # Simulate what APScheduler does: call with old-style kwargs only
    old_kwargs = {
        "channel_id": 12345,
        "message": "old reminder without scheduled time",
        "author_id": 67890,
    }
    # This should not raise TypeError about missing _scheduled_time
    # We can't fully test send_to_discord without a bot, but we can verify
    # the signature accepts the old kwargs via ** unpacking
    bound = sig.bind(**old_kwargs)
    bound.apply_defaults()
    assert bound.arguments["_scheduled_time"] is None, "_scheduled_time should default to None"


def test_send_to_discord_accepts_new_kwargs_with_scheduled_time() -> None:
    """Verify send_to_discord also works with the new _scheduled_time kwarg."""
    import inspect

    sig = inspect.signature(main.send_to_discord)
    new_kwargs = {
        "channel_id": 12345,
        "message": "new reminder with scheduled time",
        "author_id": 67890,
        "_scheduled_time": "2026-06-03T12:00:00",
    }
    bound = sig.bind(**new_kwargs)
    assert bound.arguments["_scheduled_time"] == "2026-06-03T12:00:00"


def test_send_to_user_accepts_old_kwargs_without_scheduled_time() -> None:
    """Verify send_to_user can be called with old kwargs that lack _scheduled_time.

    Same backward-compatibility guarantee as send_to_discord.
    """
    import inspect

    sig = inspect.signature(main.send_to_user)
    assert_msg = "send_to_user signature does not have _scheduled_time=None as a keyword argument"
    assert "_scheduled_time" in sig.parameters, assert_msg
    param = sig.parameters["_scheduled_time"]
    assert param.default is None, f"Expected _scheduled_time default to be None, got {param.default}"

    # Old-style kwargs (before _scheduled_time was added)
    old_kwargs = {
        "user_id": 11111,
        "guild_id": 22222,
        "message": "old DM reminder",
    }
    bound = sig.bind(**old_kwargs)
    bound.apply_defaults()
    assert bound.arguments["_scheduled_time"] is None, "_scheduled_time should default to None"


def test_send_to_user_accepts_new_kwargs_with_scheduled_time() -> None:
    """Verify send_to_user also works with the new _scheduled_time kwarg."""
    import inspect

    sig = inspect.signature(main.send_to_user)
    new_kwargs = {
        "user_id": 11111,
        "guild_id": 22222,
        "message": "new DM reminder",
        "_scheduled_time": "2026-06-03T12:00:00",
    }
    bound = sig.bind(**new_kwargs)
    assert bound.arguments["_scheduled_time"] == "2026-06-03T12:00:00"


def test_send_to_discord_accepts_pickled_snowflake_author_id() -> None:
    """Verify send_to_discord works when author_id is a Snowflake object from unpickling.

    Old reminders persisted to the APScheduler SQLite database stored author_id as a
    pickled Snowflake object (from the interactions.api.models.misc module) rather than
    a plain int. When APScheduler fires those jobs, it unpickles the kwargs and calls
    send_to_discord(**kwargs) where author_id is a Snowflake instance. This must work
    because Snowflake.__str__ returns the numeric string used in Discord mentions.
    """
    import inspect

    from interactions.api.models.misc import Snowflake

    sig = inspect.signature(main.send_to_discord)
    kwargs_with_snowflake = {
        "channel_id": 395317861578571776,
        "message": "old pickled reminder",
        "author_id": Snowflake("126462229892694018"),
    }
    # Signature binding should succeed (Python doesn't enforce type hints at runtime)
    bound = sig.bind(**kwargs_with_snowflake)
    bound.apply_defaults()
    author_id = bound.arguments["author_id"]
    assert str(author_id) == "126462229892694018", "Snowflake str() should return the numeric string"
    # Verify the f-string used in send_to_discord produces the correct mention
    mention = f"<@{author_id}>"
    assert mention == "<@126462229892694018>", f"Expected <@126462229892694018>, got {mention}"


def test_send_to_user_accepts_pickled_snowflake_user_id() -> None:
    """Verify send_to_user works when user_id is a Snowflake object from unpickling.

    Same scenario as send_to_discord — old reminders may have pickled Snowflake
    objects for user_id and guild_id instead of plain ints.
    """
    import inspect

    from interactions.api.models.misc import Snowflake

    sig = inspect.signature(main.send_to_user)
    kwargs_with_snowflake = {
        "user_id": Snowflake("11111"),
        "guild_id": Snowflake("22222"),
        "message": "old pickled DM reminder",
    }
    bound = sig.bind(**kwargs_with_snowflake)
    bound.apply_defaults()
    assert str(bound.arguments["user_id"]) == "11111"
    assert str(bound.arguments["guild_id"]) == "22222"


def test_snowflake_equality() -> None:
    """Verify Snowflake supports equality comparison with int, str, and other Snowflakes."""
    from interactions.api.models.misc import Snowflake

    sf = Snowflake("126462229892694018")

    # Snowflake == int
    assert sf == 126462229892694018, "Snowflake should equal matching int"
    assert sf != 999, "Snowflake should not equal non-matching int"

    # Snowflake == str
    assert sf == "126462229892694018", "Snowflake should equal matching str"
    assert sf != "999", "Snowflake should not equal non-matching str"

    # Snowflake == Snowflake
    assert sf == Snowflake("126462229892694018"), "Snowflakes with same value should be equal"
    assert sf != Snowflake("999"), "Snowflakes with different values should not be equal"

    # int(Snowflake) comparison still works
    assert int(sf) == 126462229892694018


def test_snowflake_hashable() -> None:
    """Verify Snowflake can be used in sets and as dict keys."""
    from interactions.api.models.misc import Snowflake

    sf1 = Snowflake("126462229892694018")
    sf2 = Snowflake("126462229892694018")
    sf3 = Snowflake("999")

    s = {sf1, sf2, sf3}
    assert len(s) == 2, "Set should deduplicate identical Snowflakes"
    assert sf1 in s
    assert sf3 in s

    d = {sf1: "value"}
    assert d[Snowflake("126462229892694018")] == "value"


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
    """Test the `parse_time` function to ensure it correctly parses a date string into a datetime object using the timezone from the environment."""
    date_to_parse = "2023-10-10 10:00:00"
    result: datetime | None = parse_time(date_to_parse, "UTC")

    assert_msg: str = "Expected datetime object, got None"
    assert result is not None, assert_msg

    assert_msg = "Expected timezone-aware datetime object, got naive datetime object"
    assert result.tzinfo is not None, assert_msg

    assert_msg = f"Expected 2023-10-10 10:00:00, got {result.strftime('%Y-%m-%d %H:%M:%S')}"
    assert result.strftime("%Y-%m-%d %H:%M:%S") == "2023-10-10 10:00:00", assert_msg
