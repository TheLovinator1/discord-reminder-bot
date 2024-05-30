"""This module contains the old scheduler used in the bot.

The old scheduler was used in version 1.0.0 of the bot.
We will migrate the jobs from this scheduler to the new one when the bot starts.
The newer version uses one database per Discord guild.

This file also has the function `migrate_jobs` that will be used to migrate the jobs
from the old scheduler to the new one.
"""

from __future__ import annotations

import os
import pickle  # noqa: S403
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from discord_reminder_bot.get_scheduler import get_scheduler
from discord_reminder_bot.send_to_discord import send_msg
from interactions.api.models.misc import Snowflake

if TYPE_CHECKING:
    import datetime

    from apscheduler.schedulers.asyncio import AsyncIOScheduler


sqlite_location: str = os.getenv(key="SQLITE_LOCATION", default="/jobs.sqlite")
logger.debug(f"{sqlite_location=}")

jobstores: dict[str, SQLAlchemyJobStore] = {
    "default": SQLAlchemyJobStore(url="sqlite:///jobs.sqlite"),
}


def find_old_db() -> str | None:
    """Find the old database."""
    # Check current directory
    current_db: Path = Path(__file__).parent / "jobs.sqlite"
    if Path(current_db).exists():
        logger.debug(f"Found old database: {current_db}")
        return str(current_db)

    # Check parent directory
    parent_dir: Path = Path(__file__).parent
    parent_db: Path = parent_dir / "jobs.sqlite"
    if Path(parent_db).exists():
        logger.debug(f"Found old database: {parent_db}")
        return str(parent_db)

    # Check grandparent directory
    grandparent_dir: Path = parent_dir.parent
    grandparent_db: Path = grandparent_dir / "jobs.sqlite"
    if Path(grandparent_db).exists():
        logger.debug(f"Found old database: {grandparent_db}")
        return str(grandparent_db)

    return None


@dataclass
class FoundJob:
    """A job found in the old scheduler."""

    # 1
    version: int

    # d552452a0d664fdf8f02160e9b36330d
    job_id: str

    # discord_reminder_bot.main:send_to_discord
    job_func: str

    # Kwargs
    # 869672947617529926
    channel_id: int

    # Remember to feed the cat!
    message: str

    # 126462229892694018
    author_id: int

    # send_to_discord
    name: str

    # datetime.datetime(2025, 11, 2, 14, 0, tzinfo=<DstTzInfo 'Europe/Stockholm' CET+1:00:00 STD>) # noqa: E501
    next_run_time: datetime.datetime


@dataclass
class IntervalJob(FoundJob):
    # <IntervalTrigger (interval=datetime.timedelta(days=365), start_date='2022-08-24 00:06:55 UTC', timezone='Etc/UTC')> # noqa: E501
    trigger: IntervalTrigger


@dataclass
class CronJob(FoundJob):
    # <CronTrigger (year='2025', month='11', day='2', hour='14', minute='0', second='0', timezone='CET') # noqa: E501
    trigger: CronTrigger


@dataclass
class DateJob(FoundJob):
    # <DateTrigger (run_date='2025-11-02 14:00:00 CET')>
    trigger: DateTrigger


def get_interval_job(job: dict) -> IntervalJob:
    """Get the interval job from the job."""
    kwargs: dict = job["kwargs"]

    author_id = kwargs["author_id"]
    if isinstance(author_id, Snowflake):
        logger.debug(f"Author ID was a Snowflake: {author_id}")
        author_id = int(author_id)

    return IntervalJob(
        version=job["version"],
        job_id=job["id"],
        job_func=job["func"],
        channel_id=kwargs["channel_id"],
        message=kwargs["message"],
        author_id=author_id,
        name=job["name"],
        next_run_time=job["next_run_time"],
        trigger=job["trigger"],
    )


def get_cron_job(job: dict) -> CronJob:
    """Get the cron job from the job."""
    kwargs: dict = job["kwargs"]

    author_id = kwargs["author_id"]
    if isinstance(author_id, Snowflake):
        logger.debug(f"Author ID was a Snowflake: {author_id}")
        author_id = int(author_id)

    return CronJob(
        version=job["version"],
        job_id=job["id"],
        job_func=job["func"],
        channel_id=kwargs["channel_id"],
        message=kwargs["message"],
        author_id=author_id,
        name=job["name"],
        next_run_time=job["next_run_time"],
        trigger=job["trigger"],
    )


def get_date_job(job: dict) -> DateJob:
    """Get the date job from the job."""
    kwargs: dict = job["kwargs"]

    author_id = kwargs["author_id"]
    if isinstance(author_id, Snowflake):
        logger.debug(f"Author ID was a Snowflake: {author_id}")
        author_id = int(author_id)

    return DateJob(
        version=job["version"],
        job_id=job["id"],
        job_func=job["func"],
        channel_id=kwargs["channel_id"],
        message=kwargs["message"],
        author_id=author_id,
        name=job["name"],
        next_run_time=job["next_run_time"],
        trigger=job["trigger"],
    )


def list_jobs() -> list[FoundJob]:
    """List all jobs from the old scheduler."""
    db_location: str | None = find_old_db()
    if db_location is None:
        logger.debug("Old database not found.")
        return []

    logger.info("Listing all jobs from the old scheduler.")

    jobs = []

    con: sqlite3.Connection = sqlite3.connect(db_location)
    cur: sqlite3.Cursor = con.cursor()
    cur.execute("SELECT * FROM apscheduler_jobs")
    rows: list[Any] = cur.fetchall()
    for row in rows:
        job_data = row[2]

        # Unpickle the job
        try:
            job = pickle.loads(job_data)  # noqa: S301
        except ModuleNotFoundError as e:
            logger.error(f"Failed to unpickle job: {e}")
            continue

        if isinstance(job["trigger"], DateTrigger):
            job = get_date_job(job)
        elif isinstance(job["trigger"], IntervalTrigger):
            job = get_interval_job(job)
        elif isinstance(job["trigger"], CronTrigger):
            job = get_cron_job(job)
        else:
            logger.error(f"Unknown trigger: {job['trigger']}")
            continue

        jobs.append(job)

        logger.info(job)

    cur.close()
    con.close()

    return jobs


def migrate_jobs() -> None:
    """Migrate the jobs from the old scheduler to the new one."""
    # TODO(TheLovinator): Migrate jobs  # noqa: TD003
    logger.info("Migrating jobs from the old scheduler.")

    old_jobs: list[FoundJob] = list_jobs()
    logger.info(f"Found {len(old_jobs)} jobs in the old scheduler.")

    for old_job in old_jobs:
        guild_id = old_job.channel_id

        trigger = (
            "IntervalTrigger"
            if isinstance(old_job, IntervalJob)
            else "CronTrigger"
            if isinstance(old_job, CronJob)
            else "DateTrigger"
        )

        scheduler: AsyncIOScheduler = get_scheduler(guild_id=guild_id)
        scheduler.add_job(
            func=send_msg,
            trigger=trigger,
            id=old_job.job_id,
            name=old_job.name,
            kwargs={
                "channel_id": old_job.channel_id,
                "message": old_job.message,
                "author_id": old_job.author_id,
            },
            next_run_time=old_job.next_run_time,
        )
        logger.debug(f"Added job '{job}' to scheduler '{scheduler=}' ({guild_id=}).")

        logger.info(f"Migrating job: {old_job}")
        add_job(guild_id=old_job.channel_id, job=old_job)


def rename_old_scheduler() -> None:
    """Rename the old scheduler database to a backup name."""
    # TODO(TheLovinator): Append a timestamp to the old scheduler database name  # noqa: TD003, E501
    # TODO(TheLovinator): We should probably add a README.txt with what we did  # noqa: TD003, E501
    # TODO(TheLovinator): Also check if all the jobs were migrated correctly  # noqa: TD003, E501
    logger.info("Renaming the old scheduler database.")
