from __future__ import annotations

import os
from pathlib import Path

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from loguru import logger

from discord_reminder_bot._config import get_scheduler_timezone
from discord_reminder_bot.helpers import generate_state

load_dotenv(verbose=True)


def get_scheduler() -> AsyncIOScheduler:
    """Return the scheduler instance.

    Uses the SQLITE_LOCATION environment variable for the SQLite database location.

    Returns:
        AsyncIOScheduler: The scheduler instance.
    """
    sqlite_location: str = os.getenv("SQLITE_LOCATION", default="/jobs.sqlite")
    logger.info(f"Using SQLite database at: {sqlite_location}")

    jobstores: dict[str, SQLAlchemyJobStore] = {"default": SQLAlchemyJobStore(url=f"sqlite://{sqlite_location}")}
    job_defaults: dict[str, bool] = {"coalesce": True}
    return AsyncIOScheduler(jobstores=jobstores, timezone=get_scheduler_timezone(), job_defaults=job_defaults)


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
            if file_path.exists() and file_path.read_text(encoding="utf-8") == job_state:
                logger.debug(f"No changes for {file_path}, skipping write.")
                continue
        except OSError as e:
            logger.error(f"Failed to save data to {file_path}: {e}")
            continue

        try:
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
