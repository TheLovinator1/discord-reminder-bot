import logging
import os

import dateparser
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


@bot.event
async def on_error(event):
    logging.error(f"{event}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        print(error)
        return
    await ctx.send(error)


@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user.name} ({bot.user.id})")


@bot.command(aliases=["reminder", "remindme", "at"])
async def remind(ctx, message_date: str, message_reason: str):
    logging.info(f"New Discord message: {ctx.message}")

    parsed_date = dateparser.parse(
        f"{message_date}",
        settings={"PREFER_DATES_FROM": "future"},
    )
    convert_date_to_our_timezone = parsed_date.astimezone(
        timezone(config_timezone))
    remove_timezone_from_date = convert_date_to_our_timezone.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    logging.debug(f"Date from command: {message_date}")
    logging.debug(f"Reason from command: {message_reason}")
    logging.debug(f"Parsed date: {parsed_date}")
    logging.debug(f"Converted date: {convert_date_to_our_timezone}")
    logging.debug(f"Date without timezone: {remove_timezone_from_date}")
    logging.debug(f"Discord channel ID: {ctx.channel.id}")
    logging.debug(f"Discord channel name: {ctx.channel.name}")

    job = scheduler.add_job(
        send_to_discord,
        run_date=remove_timezone_from_date,
        kwargs={
            "channel_id": ctx.channel.id,
            "message": message_reason,
            "author_id": ctx.message.author.id,
        },
    )
    logging.debug(
        f"Job id: '{job.id}', name: '{job.name}' and kwargs: '{job.kwargs}'")
    message = (
        f"Hello {ctx.message.author.name}, I will notify you at:\n"
        f"**{remove_timezone_from_date}**\n"
        f"With the message:\n**{message_reason}**. "
    )
    logging.debug(f"Message we sent back to user in Discord:\n {message}")
    await ctx.send(message)


async def send_to_discord(channel_id, message, author_id):
    channel = bot.get_channel(int(channel_id))
    await channel.send(f"<@{author_id}>\n{message}")


if __name__ == "__main__":
    # Environment variables
    load_dotenv(verbose=True)
    sqlite_location = os.getenv("SQLITE_LOCATION", default="/jobs.sqlite")
    config_timezone = os.getenv("TIMEZONE", default="Europe/Stockholm")
    bot_token = os.getenv("BOT_TOKEN")
    log_level = os.getenv(key="LOG_LEVEL", default="INFO")

    logging.basicConfig(level=logging.getLevelName(log_level))

    logging.info(
        f"\nsqlite_location = {sqlite_location}\n"
        f"config_timezone = {config_timezone}\n"
        f"bot_token = {bot_token}\n"
        f"log_level = {log_level}"
    )

    # Advanced Python Scheduler
    jobstores = {"default": SQLAlchemyJobStore(
        url=f"sqlite://{sqlite_location}")}
    job_defaults = {"coalesce": True}
    scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        timezone=pytz.timezone(config_timezone),
        job_defaults=job_defaults,
    )

    scheduler.start()
    bot.run(bot_token)
