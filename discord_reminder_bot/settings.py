from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytz
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from loguru import logger

from discord_reminder_bot.helpers import generate_state

load_dotenv(verbose=True)


def get_scheduler() -> AsyncIOScheduler:
    """Return the scheduler instance.

    Uses the SQLITE_LOCATION environment variable for the SQLite database location.

    Raises:
        ValueError: If the timezone is missing or invalid.

    Returns:
        AsyncIOScheduler: The scheduler instance.
    """
    config_timezone: str | None = os.getenv("TIMEZONE")
    if not config_timezone:
        msg = "Missing timezone. Please set the TIMEZONE environment variable."
        raise ValueError(msg)

    # Test if the timezone is valid
    try:
        ZoneInfo(config_timezone)
    except (ZoneInfoNotFoundError, ModuleNotFoundError) as e:
        msg: str = f"Invalid timezone: {config_timezone}. Error: {e}"
        raise ValueError(msg) from e

    logger.info(f"Using timezone: {config_timezone}. If this is incorrect, please set the TIMEZONE environment variable.")

    sqlite_location: str = os.getenv("SQLITE_LOCATION", default="/jobs.sqlite")
    logger.info(f"Using SQLite database at: {sqlite_location}")

    jobstores: dict[str, SQLAlchemyJobStore] = {"default": SQLAlchemyJobStore(url=f"sqlite://{sqlite_location}")}
    job_defaults: dict[str, bool] = {"coalesce": True}
    timezone = pytz.timezone(config_timezone)
    return AsyncIOScheduler(jobstores=jobstores, timezone=timezone, job_defaults=job_defaults)


scheduler: AsyncIOScheduler = get_scheduler()


def export_reminder_jobs_to_markdown() -> None:
    """Loop through the APScheduler database and save each job's data to a markdown file if changed."""
    data_dir: str = os.getenv("DATA_DIR", default="./data")
    logger.info(f"Exporting reminder jobs to markdown files in directory: {data_dir}")

    for job in scheduler.get_jobs():
        job_state: str = generate_state(job.__getstate__(), job)
        file_path: Path = Path(data_dir) / "reminder_data" / f"{job.id}.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if file_path.exists():
                existing_content = file_path.read_text(encoding="utf-8")
                if existing_content == job_state:
                    logger.debug(f"No changes for {file_path}, skipping write.")
                    continue
            file_path.write_text(job_state, encoding="utf-8")
            logger.info(f"Data saved to {file_path}")
        except OSError as e:
            logger.error(f"Failed to save data to {file_path}: {e}")


def get_markdown_contents_from_markdown_file(job_id: str) -> str:
    """Get the contents of a markdown file for a specific job ID.

    Args:
        job_id (str): The ID of the job.

    Returns:
        str: The contents of the markdown file, or an empty string if the file does not exist.
    """
    data_dir: str = os.getenv("DATA_DIR", default="./data")
    file_path: Path = Path(data_dir) / "reminder_data" / f"{job_id}.md"
    if file_path.exists():
        return file_path.read_text(encoding="utf-8")
    return ""
