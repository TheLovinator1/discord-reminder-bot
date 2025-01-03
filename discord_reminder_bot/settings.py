from __future__ import annotations

import os

import pytz
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv(verbose=True)
sqlite_location: str = os.getenv("SQLITE_LOCATION", default="/jobs.sqlite")
config_timezone: str = os.getenv("TIMEZONE", default="UTC")
bot_token: str = os.getenv("BOT_TOKEN", default="")
log_level: str = os.getenv("LOG_LEVEL", default="INFO")
webhook_url: str = os.getenv("WEBHOOK_URL", default="")

if not bot_token:
    err_msg = "Missing bot token"
    raise ValueError(err_msg)

# Advanced Python Scheduler
jobstores: dict[str, SQLAlchemyJobStore] = {"default": SQLAlchemyJobStore(url=f"sqlite://{sqlite_location}")}
job_defaults: dict[str, bool] = {"coalesce": True}
scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    timezone=pytz.timezone(config_timezone),
    job_defaults=job_defaults,
)
