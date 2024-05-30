from __future__ import annotations

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.base import SchedulerAlreadyRunningError
from loguru import logger

from discord_reminder_bot.database import GuildsDB, get_guild
from discord_reminder_bot.settings import DATA_DIR


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
