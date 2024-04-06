from __future__ import annotations

import os

import pytz
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(), verbose=True)
sqlite_location: str = os.getenv(key="SQLITE_LOCATION", default="/jobs.sqlite")
config_timezone: str = os.getenv(key="TIMEZONE", default="UTC")
bot_token: str = os.getenv(key="BOT_TOKEN", default="")
log_level: str = os.getenv(key="LOG_LEVEL", default="INFO")
webhook_url: str = os.getenv(key="WEBHOOK_URL", default="")

if not bot_token:
    err_msg = "Missing bot token"
    raise ValueError(err_msg)

scheduler = AsyncIOScheduler(
    jobstores={"default": SQLAlchemyJobStore(url=f"sqlite://{sqlite_location}")},
    timezone=pytz.timezone(config_timezone),
)
