from __future__ import annotations

from typing import TYPE_CHECKING

from apscheduler.triggers.date import DateTrigger
from loguru import logger

if TYPE_CHECKING:
    import datetime

    from apscheduler.job import Job


def calculate(job: Job) -> str | None:
    """Calculate the time left for a job.

    Args:
        job: The job to calculate the time for.

    Returns:
        str: The time left for the job.
    """
    trigger_time: datetime.datetime | None = job.trigger.run_date if isinstance(job.trigger, DateTrigger) else job.next_run_time

    # Check if the job is paused
    if trigger_time is None:
        logger.error(f"Couldn't calculate time for job: {job.id}")
        logger.error(f"State: {job.__getstate__() if hasattr(job, '__getstate__') else 'No state'}")
        return None

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
