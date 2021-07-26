"""
This file loads settings from environment. You can also use the .env file.

You need to fill out bot_token and config_timezone.
bot_token is from https://discord.com/developers/applications
config_timezone is TZ database name. https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
sqlite_location is where the database should be saved, default is /jobs.sqlite
log_level can be CRITICAL, ERROR, WARNING, INFO or DEBUG, default is INFO.
"""
import os

import pytz
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv(verbose=True)
sqlite_location = os.getenv("SQLITE_LOCATION", default="/jobs.sqlite")
config_timezone = os.getenv("TIMEZONE", default="Europe/Stockholm")
bot_token = os.getenv("BOT_TOKEN")
log_level = os.getenv(key="LOG_LEVEL", default="INFO")


# Advanced Python Scheduler
jobstores = {"default": SQLAlchemyJobStore(url=f"sqlite://{sqlite_location}")}
job_defaults = {"coalesce": True}
scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    timezone=pytz.timezone(config_timezone),
    job_defaults=job_defaults,
)
