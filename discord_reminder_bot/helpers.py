from __future__ import annotations

import datetime
import json
import os
from typing import Any
from zoneinfo import ZoneInfo

import dateparser
from apscheduler.job import Job
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from interactions.api.models.misc import Snowflake


def calculate(job: Job) -> str:
    """Calculate the time left for a job.

    Args:
        job: The job to calculate the time for.

    Returns:
        str: The time left for the job or "Paused" if the job is paused or has no next run time.
    """
    trigger_time = None
    if isinstance(job.trigger, DateTrigger | IntervalTrigger):
        trigger_time = job.next_run_time or None

    elif isinstance(job.trigger, CronTrigger):
        if not job.next_run_time:
            logger.debug(f"No next run time found for '{job.id}', probably paused? {job.__getstate__()}")
            return "Paused"

        trigger_time = job.trigger.get_next_fire_time(None, datetime.datetime.now(tz=job._scheduler.timezone))  # noqa: SLF001

    logger.debug(f"{type(job.trigger)=}, {trigger_time=}")

    if not trigger_time:
        logger.debug("No trigger time found")
        return "Paused"

    return f"<t:{int(trigger_time.timestamp())}:R>"


def get_human_readable_time(job: Job) -> str:
    """Get the human-readable time for a job.

    Args:
        job: The job to get the time for.

    Returns:
        str: The human-readable time.
    """
    trigger_time = None
    if isinstance(job.trigger, DateTrigger | IntervalTrigger):
        trigger_time = job.next_run_time or None

    elif isinstance(job.trigger, CronTrigger):
        if not job.next_run_time:
            logger.debug(f"No next run time found for '{job.id}', probably paused? {job.__getstate__()}")
            return "Paused"

        trigger_time = job.trigger.get_next_fire_time(None, datetime.datetime.now(tz=job._scheduler.timezone))  # noqa: SLF001

    if not trigger_time:
        logger.debug("No trigger time found")
        return "Paused"

    return trigger_time.strftime("%Y-%m-%d %H:%M:%S")


def parse_time(date_to_parse: str | None, timezone: str | None = os.getenv("TIMEZONE")) -> datetime.datetime | None:
    """Parse a date string into a datetime object.

    Args:
        date_to_parse(str): The date string to parse.
        timezone(str, optional): The timezone to use. Defaults to the TIMEZONE environment variable.

    Returns:
        datetime.datetime: The parsed datetime object.
    """
    if not date_to_parse:
        logger.error("No date provided to parse.")
        return None

    if not timezone:
        logger.error("No timezone provided to parse date.")
        return None

    logger.info(f"Parsing date: '{date_to_parse}' with timezone: '{timezone}'")

    try:
        parsed_date: datetime.datetime | None = dateparser.parse(
            date_string=date_to_parse,
            settings={
                "PREFER_DATES_FROM": "future",
                "TIMEZONE": f"{timezone}",
                "RETURN_AS_TIMEZONE_AWARE": True,
                "RELATIVE_BASE": datetime.datetime.now(tz=ZoneInfo(str(timezone))),
            },
        )
    except (ValueError, TypeError) as e:
        logger.error(f"Failed to parse date: '{date_to_parse}' with timezone: '{timezone}'. Error: {e}")
        return None

    logger.debug(f"Parsed date: {parsed_date} from '{date_to_parse}'")

    return parsed_date


def generate_state(state: dict[str, Any], job: Job) -> str:
    """Format the __getstate__ dictionary for Discord markdown.

    Args:
        state (dict): The __getstate__ dictionary.
        job (Job): The APScheduler job.

    Returns:
        str: The formatted string.
    """
    if not state:
        logger.error(f"No state found for {job.id}")
        return "No state found.\n"

    for key, value in state.items():
        if isinstance(value, IntervalTrigger):
            state[key] = "IntervalTrigger"
        elif isinstance(value, DateTrigger):
            state[key] = "DateTrigger"
        elif isinstance(value, Job):
            state[key] = "Job"
        elif isinstance(value, Snowflake):
            state[key] = str(value)

    try:
        msg: str = json.dumps(state, indent=4, default=str)
    except TypeError as e:
        e.add_note("This is likely due to a non-serializable object in the state. Please check the state for any non-serializable objects.")
        e.add_note(f"{state=}")
        logger.error(f"Failed to serialize state: {e}")
        return "Failed to serialize state."

    return msg


def generate_markdown_state(state: dict[str, Any], job: Job) -> str:
    """Format the __getstate__ dictionary for Discord markdown.

    Args:
        state (dict): The __getstate__ dictionary.
        job (Job): The APScheduler job.

    Returns:
        str: The formatted string.
    """
    msg: str = generate_state(state=state, job=job)
    return "```json\n" + msg + "\n```"
