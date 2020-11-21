import logging
import os

import dateparser
import dhooks
import discord
import pytz
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext import commands
from dotenv import load_dotenv
from pytz import timezone

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    description="Reminder bot for Discord by TheLovinator#9276",
    intents=intents,
)
logging.basicConfig(level=logging.DEBUG)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")


@bot.command(aliases=["reminder"])
async def remind(ctx, message_date: str, message_reason: str):
    print("remind - ---------------------")
    print(f"remind - Message: {ctx.message}")

    parsed_date = dateparser.parse(
        f"{message_date}",
        settings={"PREFER_DATES_FROM": "future"},
    )
    convert_date_to_our_timezone = parsed_date.astimezone(timezone(config_timezone))
    remove_timezone_from_date = convert_date_to_our_timezone.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    print(f"remind - Date from command: {message_date}")
    print(f"remind - Reason from command: {message_reason}")
    print(f"remind - Parsed Date: {parsed_date}")
    print(f"remind - Converted date: {convert_date_to_our_timezone}")
    print(f"remind - Date without timezone: {remove_timezone_from_date}")
    print(f"remind - Channel ID: {ctx.channel.id}")
    print(f"remind - Channel name: {ctx.channel.name}")

    job = scheduler.add_job(
        send_to_discord,
        run_date=remove_timezone_from_date,
        kwargs={
            "webhook_url": webhook_url,
            "message": message_reason,
        },
    )
    print(f"remind - Id: {job.id}, Name: {job.name}, kwargs: {job.kwargs}")
    message = f"I will notify you at `{remove_timezone_from_date}` with the message `{message_reason}`."
    print(f"remind - Message we sent back to user in Discord: {message}")
    await ctx.send(message)


async def send_to_discord(webhook_url, message):
    print(f"send_to_discord - Webhook url: {webhook_url}")
    print(f"send_to_discord - Message: {message}")
    hook = dhooks.Webhook(webhook_url)
    hook.send(message)


if __name__ == "__main__":
    # Enviroment variables
    load_dotenv(verbose=True)
    webhook_url = os.getenv("WEBHOOK_URL")  # TODO: Read this directly from the server
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

    scheduler.start()
    bot.run(bot_token)
