from __future__ import annotations

from typing import TYPE_CHECKING

from apscheduler.jobstores.base import JobLookupError
from loguru import logger

from discord_reminder_bot.get_scheduler import get_scheduler

if TYPE_CHECKING:
    from apscheduler.job import Job
    from apscheduler.schedulers.asyncio import AsyncIOScheduler


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
