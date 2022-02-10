"""Test discord-reminder-bot.

Jobs are stored in memory.
"""
import re

import dateparser
import pytz
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from discord_reminder_bot import __version__
from discord_reminder_bot.main import calc_countdown, send_to_discord


def test_version():
    """Check if version is 0.2.0."""
    assert __version__ == "0.2.0"


class TestClass:
    """This tests everything.

    This sets up sqlite database in memory, changes scheduler timezone
    to Europe/Stockholm and creates job that runs January 18 2040.
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

    run_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")  # type: ignore
    job = scheduler.add_job(
        send_to_discord,
        run_date=run_date,
        kwargs={
            "channel_id": 865712621109772329,
            "message": "Running PyTest",
            "author_id": 126462229892694018,
        },
    )

    def test_calc_countdown(self):
        """Check if calc_countdown returns days, hours and minutes."""
        # FIXME: This will break when there is 0 seconds/hours/days left
        pattern = re.compile(r"\d* days, \d* hours, \d* minutes")
        countdown = calc_countdown(self.job)
        assert pattern.match(countdown)
