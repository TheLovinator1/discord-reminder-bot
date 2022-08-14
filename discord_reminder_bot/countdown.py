import datetime

import pytz
from apscheduler.job import Job
from apscheduler.triggers.date import DateTrigger

from discord_reminder_bot.settings import config_timezone


def calculate(job: Job) -> str:
    """Get trigger time from a reminder and calculate how many days,
    hours and minutes till trigger.

    Days/Minutes will not be included if 0.

    Args:
        job: The job. Can be cron, interval or normal.

    Returns:
        Returns days, hours and minutes till reminder. Returns "Failed to calculate time" if no job is found.
    """
    # TODO: This "breaks" when only seconds are left.
    # If we use (in {calc_countdown(job)}) it will show (in )

    if type(job.trigger) is DateTrigger:
        trigger_time = job.trigger.run_date
    else:
        trigger_time = job.next_run_time

    # Get_job() returns None when it can't find a job with that id.
    if trigger_time is None:
        # TODO: Change this to None and send this text where needed.
        return "Failed to calculate time"

    # Get time and date the job will run and calculate how many days,
    # hours and seconds.
    countdown = trigger_time - datetime.datetime.now(tz=pytz.timezone(config_timezone))

    days, hours, minutes = (
        countdown.days,
        countdown.seconds // 3600,
        countdown.seconds // 60 % 60,
    )

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
