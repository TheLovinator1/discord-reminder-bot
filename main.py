import datetime
import logging
import os

import dateparser
import discord
import pytz
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext import commands
from dotenv import load_dotenv

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


@bot.command()
async def jobs(ctx):
    msg = ""
    jobs = scheduler.get_jobs()
    for job in jobs:
        channel_id = job.kwargs.get("channel_id")
        for channel in ctx.guild.channels:
            if channel.id == channel_id:
                message = job.kwargs.get("message")

                trigger_time = job.trigger.run_date
                countdown = trigger_time - datetime.datetime.now(
                    tz=pytz.timezone(config_timezone)
                )
                days, hours, minutes = (
                    countdown.days,
                    countdown.seconds // 3600,
                    countdown.seconds // 60 % 60,
                )

                the_final_countdown = ""
                if days != 0:
                    the_final_countdown += f"{days} days, "
                if hours != 0:
                    the_final_countdown += f"{hours} hours, "
                if minutes != 0:
                    the_final_countdown += f"{minutes} minutes"

                msg += f'{message} at {trigger_time.strftime("%Y-%m-%d %H:%M:%S")} (in {the_final_countdown})\n'
    if not msg:
        msg = "This server has no reminders."
    await ctx.send(msg)


@bot.command(aliases=["reminder", "remindme", "at"])
async def remind(ctx, message_date: str, message_reason: str):
    logging.info(f"New Discord message: {ctx.message}")

    parsed_date = dateparser.parse(
        f"{message_date}",
        settings={
            "PREFER_DATES_FROM": "future",
            "TO_TIMEZONE": f"{config_timezone}",
        },
    )
    remove_timezone_from_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")

    logging.debug(f"Date from command: {message_date}")
    logging.debug(f"Reason from command: {message_reason}")
    logging.debug(f"Parsed date: {parsed_date}")
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
    logging.debug(f"Job id: '{job.id}', name: '{job.name}' and kwargs: '{job.kwargs}'")
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
    jobstores = {"default": SQLAlchemyJobStore(url=f"sqlite://{sqlite_location}")}
    job_defaults = {"coalesce": True}
    scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        timezone=pytz.timezone(config_timezone),
        job_defaults=job_defaults,
    )

    scheduler.start()
    bot.run(bot_token)
