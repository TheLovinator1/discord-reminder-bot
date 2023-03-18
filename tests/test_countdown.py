from datetime import datetime

import dateparser
import pytz
from apscheduler.job import Job
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from discord_reminder_bot.main import send_to_discord


class TestCountdown:
    """This tests everything.

    This sets up sqlite database in memory, changes scheduler timezone
    to Europe/Stockholm and creates job that runs January 18 2040 and one that
    runs at 00:00.
    """

    jobstores: dict[str, SQLAlchemyJobStore] = {"default": SQLAlchemyJobStore(url="sqlite:///:memory")}
    job_defaults: dict[str, bool] = {"coalesce": True}
    scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        timezone=pytz.timezone("Europe/Stockholm"),
        job_defaults=job_defaults,
    )

    parsed_date: datetime | None = dateparser.parse(
        "18 January 2040",
        settings={
            "PREFER_DATES_FROM": "future",
            "TO_TIMEZONE": "Europe/Stockholm",
        },
    )
    assert parsed_date

    run_date: str = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
    job: Job = scheduler.add_job(
        send_to_discord,
        run_date=run_date,
        kwargs={
            "channel_id": 865712621109772329,
            "message": "Running PyTest",
            "author_id": 126462229892694018,
        },
    )

    timezone_date: datetime | None = dateparser.parse(
        "00:00",
        settings={
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": "Europe/Stockholm",
            "TO_TIMEZONE": "Europe/Stockholm",
        },
    )

    assert timezone_date
    timezone_run_date: str = timezone_date.strftime("%Y-%m-%d %H:%M:%S")
    timezone_job: Job = scheduler.add_job(
        send_to_discord,
        run_date=timezone_run_date,
        kwargs={
            "channel_id": 865712621109772329,
            "message": "Running PyTest at 00:00",
            "author_id": 126462229892694018,
        },
    )

    timezone_date2: datetime | None = dateparser.parse(
        "13:37",
        settings={
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": "Europe/Stockholm",
            "TO_TIMEZONE": "Europe/Stockholm",
        },
    )

    assert timezone_date2
    timezone_run_date2: str = timezone_date2.strftime("%Y-%m-%d %H:%M:%S")
    timezone_job2: Job = scheduler.add_job(
        send_to_discord,
        run_date=timezone_run_date2,
        kwargs={
            "channel_id": 865712621109772329,
            "message": "Running PyTest at 13:37",
            "author_id": 126462229892694018,
        },
    )

    def test_if_timezones_are_working(self) -> None:  # noqa: ANN101
        """Check if timezones are working.

        Args:
            self: TestCountdown
        """
        time_job: Job | None = self.scheduler.get_job(self.timezone_job.id)
        assert time_job

        assert time_job.trigger.run_date.hour == 0
        assert time_job.trigger.run_date.minute == 0
        assert time_job.trigger.run_date.second == 0

        time_job2: Job | None = self.scheduler.get_job(self.timezone_job2.id)
        assert time_job2

        assert time_job2.trigger.run_date.hour == 13  # noqa: PLR2004
        assert time_job2.trigger.run_date.minute == 37  # noqa: PLR2004
        assert time_job2.trigger.run_date.second == 0
