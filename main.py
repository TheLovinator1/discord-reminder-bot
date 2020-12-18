import datetime
import logging
import os
import traceback

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
logging.basicConfig(level=logging.DEBUG)


@bot.event
async def on_error(event):
    embed = discord.Embed(title=":x: Event Error", colour=0xE74C3C)  # Red
    embed.add_field(name="Event", value=event)
    embed.description = "```py\n%s\n```" % traceback.format_exc()
    embed.timestamp = datetime.datetime.utcnow()
    await bot.AppInfo.owner.send(embed=embed)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        print(error)
        return
    await ctx.send(error)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")


@bot.command(aliases=["reminder", "remindme", "at"])
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
            "channel_id": ctx.channel.id,
            "message": message_reason,
            "author_id": ctx.message.author.id,
        },
    )
    print(f"remind - Id: {job.id}, Name: {job.name}, kwargs: {job.kwargs}")
    message = f"Hello {ctx.message.author.name}, I will notify you at:\n**{remove_timezone_from_date}**\nWith " \
              f"message:\n**{message_reason}**. "
    print(f"remind - Message we sent back to user in Discord: {message}")
    await ctx.send(message)


async def send_to_discord(channel_id, message, author_id):
    print(f"send_to_discord - Channel ID: {channel_id}")
    print(f"send_to_discord - Author ID: {author_id}")
    print(f"send_to_discord - Message: {message}")
    channel = bot.get_channel(int(channel_id))
    await channel.send(f"<@{author_id}>\n{message}")


if __name__ == "__main__":
    # Environment variables
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

    scheduler.start()
    bot.run(bot_token)
