import os

import pytz
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv(verbose=True)
sqlite_location = os.getenv("SQLITE_LOCATION", default="/jobs.sqlite")
config_timezone = os.getenv("TIMEZONE", default="Europe/Stockholm")
bot_token = os.getenv("BOT_TOKEN", default="")
log_level = os.getenv(key="LOG_LEVEL", default="INFO")

if not bot_token:
    raise ValueError("Missing bot token")

# Advanced Python Scheduler
jobstores = {"default": SQLAlchemyJobStore(url=f"sqlite://{sqlite_location}")}
job_defaults = {"coalesce": True}
scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    timezone=pytz.timezone(config_timezone),
    job_defaults=job_defaults,
)
