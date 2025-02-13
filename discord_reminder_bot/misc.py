from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

if TYPE_CHECKING:
    from apscheduler.job import Job


def calculate(job: Job) -> str | None:
    """Calculate the time left for a job.

    Args:
        job: The job to calculate the time for.

    Returns:
        str: The time left for the job.
    """
    trigger_time = None
    if isinstance(job.trigger, DateTrigger | IntervalTrigger):
        trigger_time = job.next_run_time if hasattr(job, "next_run_time") else None
    elif isinstance(job.trigger, CronTrigger):
        trigger_time = job.trigger.get_next_fire_time(None, datetime.datetime.now(tz=job._scheduler.timezone))  # noqa: SLF001

    if not trigger_time:
        return "Paused"

    return f"<t:{int(trigger_time.timestamp())}:R>"


def get_human_time(time: datetime.timedelta) -> str:
    """Convert timedelta to human-readable format.

    Args:
        time: The timedelta to convert.

    Returns:
        str: The human-readable time.
    """
    days, seconds = divmod(time.total_seconds(), 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    time_str: str = ""
    if days:
        time_str += f"{int(days)}d"
    if hours:
        time_str += f"{int(hours)}h"
    if minutes:
        time_str += f"{int(minutes)}m"
    if seconds:
        time_str += f"{int(seconds)}s"

    return time_str


def calc_time(time: datetime.datetime | None) -> str:
    """Convert a datetime object to a Discord timestamp.

    Args:
        time: The datetime object to convert.

    Returns:
        str: The Discord timestamp.
    """
    if not time:
        return "None"

    return f"<t:{int(time.timestamp())}:R>"
