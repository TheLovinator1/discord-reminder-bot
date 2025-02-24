from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

if TYPE_CHECKING:
    from apscheduler.job import Job


def calculate(job: Job) -> str:
    """Calculate the time left for a job.

    Args:
        job: The job to calculate the time for.

    Returns:
        str: The time left for the job.
    """
    trigger_time = None
    if isinstance(job.trigger, DateTrigger | IntervalTrigger):
        trigger_time = job.next_run_time or None

    elif isinstance(job.trigger, CronTrigger):
        if not job.next_run_time:
            logger.debug("No next run time found so probably paused?")
            return "Paused"

        trigger_time = job.trigger.get_next_fire_time(None, datetime.datetime.now(tz=job._scheduler.timezone))  # noqa: SLF001

    logger.debug(f"{type(job.trigger)=}, {trigger_time=}")

    if not trigger_time:
        logger.debug("No trigger time found")
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
