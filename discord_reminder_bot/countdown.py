from datetime import datetime, timedelta

import pytz
from apscheduler.job import Job
from apscheduler.triggers.date import DateTrigger

from discord_reminder_bot.settings import config_timezone


def calculate(job: Job) -> str:
    """Get trigger time from a reminder and calculate how many days, hours and minutes till trigger.

    Days/Minutes will not be included if 0.

    Args:
        job: The job. Can be cron, interval or normal.

    Returns:
        Returns days, hours and minutes till the reminder. Returns "Couldn't calculate time" if no job is found.
    """
    # TODO: This "breaks" when only seconds are left.
    # If we use (in {calc_countdown(job)}) it will show (in )

    trigger_time: datetime | None = job.trigger.run_date if type(job.trigger) is DateTrigger else job.next_run_time

    # Get_job() returns None when it can't find a job with that ID.
    if trigger_time is None:
        # TODO: Change this to None and send this text where needed.
        return "Couldn't calculate time"

    # Get time and date the job will run and calculate how many days,
    # hours and seconds.
    return countdown(trigger_time)


def countdown(trigger_time: datetime) -> str:
    """Calculate days, hours and minutes to a date.

    Args:
        trigger_time: The date.

    Returns:
        A string with the days, hours and minutes.
    """
    countdown_time: timedelta = trigger_time - datetime.now(tz=pytz.timezone(config_timezone))

    days, hours, minutes = (
        countdown_time.days,
        countdown_time.seconds // 3600,
        countdown_time.seconds // 60 % 60,
    )

    # Return seconds if only seconds are left.
    if days == 0 and hours == 0 and minutes == 0:
        seconds: int = countdown_time.seconds % 60
        return f"{seconds} second" + ("s" if seconds != 1 else "")

    # TODO: Explain this.
    return ", ".join(
        f"{x} {y}{'s' * (x != 1)}"
        for x, y in (
            (days, "day"),
            (hours, "hour"),
            (minutes, "minute"),
        )
        if x
    )
