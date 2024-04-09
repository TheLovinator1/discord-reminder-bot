from __future__ import annotations

from typing import TYPE_CHECKING

from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.base import SchedulerAlreadyRunningError
from loguru import logger

from discord_reminder_bot.database import GuildsDB, get_guild
from discord_reminder_bot.settings import DATA_DIR

if TYPE_CHECKING:
    from apscheduler.job import Job


def get_scheduler(guild_id: int) -> AsyncIOScheduler:
    """Create a new scheduler.

    This function creates a new scheduler with a SQLite job store.

    Args:
        guild_id: The guild id.

    Returns:
        AsyncIOScheduler: The new scheduler.
    """
    url: str = f"sqlite:///{DATA_DIR / f'{guild_id}.sqlite'}"
    logger.debug(f"{url=}")
    guild: GuildsDB = get_guild(guild_id=guild_id)

    jobstores: dict[str, SQLAlchemyJobStore] = {
        "default": SQLAlchemyJobStore(url=url),
    }
    scheduler = AsyncIOScheduler(jobstores=jobstores, timezone=guild.timezone)

    try:
        scheduler.start()
    except SchedulerAlreadyRunningError:
        logger.warning(f"Scheduler '{scheduler=}' ({guild_id=}) is already running.")
    return scheduler


def list_jobs(guild_id: int) -> list[str]:
    """List all jobs in the scheduler.

    Args:
        guild_id: The guild id.

    Returns:
        list[str]: A list of all jobs in the scheduler.
    """
    scheduler: AsyncIOScheduler = get_scheduler(guild_id=guild_id)
    jobs: list[Job] = scheduler.get_jobs()
    return [str(job) for job in jobs]


def remove_job(guild_id: int, job_id: str) -> None:
    """Remove a job from the scheduler.

    Args:
        guild_id: The guild id.
        job_id: The job id.

    Returns:
        None
    """
    scheduler: AsyncIOScheduler = get_scheduler(guild_id=guild_id)
    try:
        scheduler.remove_job(job_id=job_id)

    except JobLookupError:
        logger.error(
            f"Could not find job '{job_id}' in scheduler '{scheduler=}' ({guild_id=}).",
        )
    logger.debug(f"Removed job '{job_id}' from scheduler '{scheduler=}' ({guild_id=}).")


def disable_job(guild_id: int, job_id: str) -> None:
    """Disable a job in the scheduler.

    Args:
        guild_id: The guild id.
        job_id: The job id.

    Returns:
        None
    """
    scheduler: AsyncIOScheduler = get_scheduler(guild_id=guild_id)
    try:
        scheduler.pause_job(job_id=job_id)

    except JobLookupError:
        logger.error(
            f"Could not find job '{job_id}' in scheduler '{scheduler=}' ({guild_id=}).",
        )
    logger.debug(f"Disabled job '{job_id}' in scheduler '{scheduler=}' ({guild_id=}).")


def enable_job(guild_id: int, job_id: str) -> None:
    """Enable a job in the scheduler.

    Args:
        guild_id: The guild id.
        job_id: The job id.

    Returns:
        None
    """
    scheduler: AsyncIOScheduler = get_scheduler(guild_id=guild_id)
    try:
        scheduler.resume_job(job_id=job_id)

    except JobLookupError:
        logger.error(
            f"Could not find job '{job_id}' in scheduler '{scheduler=}' ({guild_id=}).",
        )
    logger.debug(f"Enabled job '{job_id}' in scheduler '{scheduler=}' ({guild_id=}).")


def shutdown_scheduler(guild_id: int) -> None:
    """Shutdown the scheduler.

    Args:
        guild_id: The guild id.

    Returns:
        None
    """
    scheduler: AsyncIOScheduler = get_scheduler(guild_id=guild_id)
    scheduler.shutdown()
    logger.debug(f"Shutdown scheduler '{scheduler=}' ({guild_id=}).")
