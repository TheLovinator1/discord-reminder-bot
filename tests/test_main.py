from __future__ import annotations

import zoneinfo
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest
from apscheduler.job import Job
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from discord_reminder_bot import main
from discord_reminder_bot.main import calculate, parse_time

if TYPE_CHECKING:
    from apscheduler.job import Job


def dummy_job() -> None:
    """Dummy job function for testing."""


def test_calculate() -> None:
    """Test the calculate function with various job inputs."""
    scheduler = BackgroundScheduler()
    scheduler.timezone = timezone.utc
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


def test_if_send_to_discord_is_in_main() -> None:
    """send_to_discords needs to be in main for this program to work."""
    assert_msg: str = f"send_to_discord is not in main. Current functions in main: {dir(main)}"
    assert hasattr(main, "send_to_discord"), assert_msg


def test_if_send_to_user_is_in_main() -> None:
    """send_to_user needs to be in main for this program to work."""
    assert_msg: str = f"send_to_user is not in main. Current functions in main: {dir(main)}"
    assert hasattr(main, "send_to_user"), assert_msg


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
