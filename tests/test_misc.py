from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from apscheduler.job import Job
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from discord_reminder_bot.misc import calc_time, calculate, get_human_time

if TYPE_CHECKING:
    from apscheduler.job import Job


def test_calc_time() -> None:
    """Test the calc_time function with various datetime inputs."""
    test_datetime: datetime = datetime(2023, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    expected_timestamp: str = f"<t:{int(test_datetime.timestamp())}:R>"
    assert_msg = f"Expected {expected_timestamp}, got {calc_time(test_datetime)}"
    assert calc_time(test_datetime) == expected_timestamp, assert_msg

    now: datetime = datetime.now(tz=timezone.utc)
    expected_timestamp_now: str = f"<t:{int(now.timestamp())}:R>"
    assert_msg = f"Expected {expected_timestamp_now}, got {calc_time(now)}"
    assert calc_time(now) == expected_timestamp_now, assert_msg

    past_datetime: datetime = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    expected_timestamp_past: str = f"<t:{int(past_datetime.timestamp())}:R>"
    assert_msg = f"Expected {expected_timestamp_past}, got {calc_time(past_datetime)}"
    assert calc_time(past_datetime) == expected_timestamp_past, assert_msg

    future_datetime: datetime = datetime(2100, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    expected_timestamp_future: str = f"<t:{int(future_datetime.timestamp())}:R>"
    assert_msg: str = f"Expected {expected_timestamp_future}, got {calc_time(future_datetime)}"
    assert calc_time(future_datetime) == expected_timestamp_future, assert_msg


def test_get_human_time() -> None:
    """Test the get_human_time function with various timedelta inputs."""
    test_timedelta = timedelta(days=1, hours=2, minutes=3, seconds=4)
    expected_output: str = "1d2h3m4s"
    assert_msg: str = f"Expected {expected_output}, got {get_human_time(test_timedelta)}"
    assert get_human_time(test_timedelta) == expected_output, assert_msg

    test_timedelta = timedelta(hours=5, minutes=6, seconds=7)
    expected_output: str = "5h6m7s"
    assert_msg = f"Expected {expected_output}, got {get_human_time(test_timedelta)}"
    assert get_human_time(test_timedelta) == expected_output, assert_msg

    test_timedelta = timedelta(minutes=8, seconds=9)
    expected_output: str = "8m9s"
    assert_msg = f"Expected {expected_output}, got {get_human_time(test_timedelta)}"
    assert get_human_time(test_timedelta) == expected_output, assert_msg

    test_timedelta = timedelta(seconds=10)
    expected_output: str = "10s"
    assert_msg = f"Expected {expected_output}, got {get_human_time(test_timedelta)}"
    assert get_human_time(test_timedelta) == expected_output, assert_msg

    test_timedelta = timedelta(days=0, hours=0, minutes=0, seconds=0)
    expected_output: str = ""
    assert_msg = f"Expected {expected_output}, got {get_human_time(test_timedelta)}"
    assert get_human_time(test_timedelta) == expected_output, assert_msg


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
