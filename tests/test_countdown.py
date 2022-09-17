"""Test discord-reminder-bot.

Jobs are stored in memory.
"""
import re
from sched import scheduler

import dateparser
import pytz
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from discord_reminder_bot.countdown import calculate
from discord_reminder_bot.main import send_to_discord


class TestCountdown:
    """This tests everything.

    This sets up sqlite database in memory, changes scheduler timezone
    to Europe/Stockholm and creates job that runs January 18 2040 and one that
    runs at 00:00.
    """

    jobstores = {"default": SQLAlchemyJobStore(url="sqlite:///:memory")}
    job_defaults = {"coalesce": True}
    scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        timezone=pytz.timezone("Europe/Stockholm"),
        job_defaults=job_defaults,
    )

    parsed_date = dateparser.parse(
        "18 January 2040",
        settings={
            "PREFER_DATES_FROM": "future",
            "TO_TIMEZONE": "Europe/Stockholm",
        },
    )
    run_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
    job = scheduler.add_job(
        send_to_discord,
        run_date=run_date,
        kwargs={
            "channel_id": 865712621109772329,
            "message": "Running PyTest",
            "author_id": 126462229892694018,
        },
    )

    timezone_date = dateparser.parse(
        "00:00",
        settings={
            "PREFER_DATES_FROM": "future",
            "TO_TIMEZONE": "Europe/Stockholm",
        },
    )
    timezone_run_date = timezone_date.strftime("%Y-%m-%d %H:%M:%S")
    timezone_job = scheduler.add_job(
        send_to_discord,
        run_date=timezone_run_date,
        kwargs={
            "channel_id": 865712621109772329,
            "message": "Running PyTest at 00:00",
            "author_id": 126462229892694018,
        },
    )

    timezone_date2 = dateparser.parse(
        "13:37",
        settings={
            "PREFER_DATES_FROM": "future",
            "TO_TIMEZONE": "Europe/Stockholm",
        },
    )
    timezone_run_date2 = timezone_date2.strftime("%Y-%m-%d %H:%M:%S")
    timezone_job2 = scheduler.add_job(
        send_to_discord,
        run_date=timezone_run_date2,
        kwargs={
            "channel_id": 865712621109772329,
            "message": "Running PyTest at 13:37",
            "author_id": 126462229892694018,
        },
    )

    def test_countdown(self):
        """Check if calc_countdown returns days, hours and minutes."""
        # FIXME: This will break when there is 0 seconds/hours/days left
        pattern = re.compile(r"\d* (day|days), \d* (hour|hours). \d* (minute|minutes)")
        countdown = calculate(self.job)
        assert pattern.match(countdown)

    def test_if_timezones_are_working(self):
        """Check if timezones are working."""
        time_job = self.scheduler.get_job(self.timezone_job.id)
        assert time_job.trigger.run_date.hour == 0
        assert time_job.trigger.run_date.minute == 0
        assert time_job.trigger.run_date.second == 0

        time_job2 = self.scheduler.get_job(self.timezone_job2.id)
        assert time_job2.trigger.run_date.hour == 13
        assert time_job2.trigger.run_date.minute == 37
        assert time_job2.trigger.run_date.second == 0
