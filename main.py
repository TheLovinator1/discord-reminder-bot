import datetime
import logging
import os

import dateparser
import discord
import pytz
from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext
from discord_slash.model import SlashCommandOptionType
from discord_slash.utils.manage_commands import create_option
from dotenv import load_dotenv

# guild_ids = [341001473661992962, 98905546077241344]

bot = commands.Bot(
    command_prefix="!",
    description="Reminder bot for Discord by TheLovinator#9276",
    intents=discord.Intents.all(),  # TODO: Find the actual intents we need.
    # https://discordpy.readthedocs.io/en/latest/api.html#discord.Intents
)
slash = SlashCommand(bot, sync_commands=True)


def countdown(remind_id: str) -> str:
    job = scheduler.get_job(remind_id)

    # Get_job() returns None when it can't find a job with that id.
    if job is None:
        print(f"No reminder with that ID ({remind_id}).")
        return "0 days, 0 hours, 0 minutes"

    # Get time and date the job will run and calculate how many days, hours and seconds.
    trigger_time = job.trigger.run_date
    countdown = trigger_time - datetime.datetime.now(tz=pytz.timezone(config_timezone))

    days, hours, minutes = (
        countdown.days,
        countdown.seconds // 3600,
        countdown.seconds // 60 % 60,
    )
    the_final_countdown = ", ".join(
        f"{x} {y}{'s'*(x!=1)}"
        for x, y in (
            (days, "day"),
            (hours, "hour"),
            (minutes, "minute"),
        )
        if x
    )
    return the_final_countdown


@bot.event
async def on_error(event, *args, **kwargs):
    logging.error(f"{event}")


@bot.event
async def on_slash_command_error(ctx, ex):
    logging.error(f"{ex}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    await ctx.send(error)


@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user.name}")


@slash.subcommand(
    base="remind",
    name="modify",
    description="Modify a reminder.",
    options=[
        create_option(
            name="remind_id",
            description="ID for reminder we should modify. ID can be found with /remind list",
            option_type=SlashCommandOptionType.STRING,
            required=True,
        ),
        create_option(
            name="new_message_reason",
            description="New message.",
            option_type=SlashCommandOptionType.STRING,
            required=False,
        ),
        create_option(
            name="new_message_date",
            description="New date.",
            option_type=SlashCommandOptionType.STRING,
            required=False,
        ),
    ],
)
async def remind_modify(
    ctx: SlashContext, remind_id: str, new_message_reason=None, new_message_date=None
):
    job = scheduler.get_job(remind_id)

    # Get_job() returns None when it can't find a job with that id.
    if job is None:
        await ctx.send(f"No reminder with that ID ({remind_id}).")
        return

    message = job.kwargs.get("message")
    the_final_countdown_old = countdown(job.id)

    channel_name = bot.get_channel(int(job.kwargs.get("channel_id")))
    msg = f"**Modified** {remind_id} in #{channel_name}\n"
    if new_message_reason:
        try:
            scheduler.modify_job(
                remind_id,
                kwargs={
                    "channel_id": job.kwargs.get("channel_id"),
                    "message": new_message_reason,
                    "author_id": job.kwargs.get("author_id"),
                },
            )
        except JobLookupError as e:
            await ctx.send(e)
        msg += f"**Old message**: {message}\n**New message**: {new_message_reason}\n"

    if new_message_date:
        parsed_date = dateparser.parse(
            f"{new_message_date}",
            settings={
                "PREFER_DATES_FROM": "future",
                "TO_TIMEZONE": f"{config_timezone}",
            },
        )

        remove_timezone_from_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
        try:
            job = scheduler.reschedule_job(
                remind_id, run_date=remove_timezone_from_date
            )
        except JobLookupError:
            await ctx.send(f"No job by the id of {remind_id} was found")

        remove_timezone_from_date_old = job.trigger.run_date.strftime("%Y-%m-%d %H:%M")
        the_final_countdown_new = countdown(remind_id)
        msg += (
            f"**Old date**: {remove_timezone_from_date_old} (in {the_final_countdown_old})\n"
            f"**New date**: {remove_timezone_from_date} (in {the_final_countdown_new})"
        )

    await ctx.send(msg)


@slash.subcommand(
    base="remind",
    name="remove",
    description="Remove a reminder.",
    options=[
        create_option(
            name="remind_id",
            description="ID for reminder we should remove. ID can be found with /remind list",
            option_type=SlashCommandOptionType.STRING,
            required=True,
        ),
    ],
)
async def remind_remove(ctx: SlashContext, remind_id: str):
    job = scheduler.get_job(remind_id)
    if job is None:
        await ctx.send(f"No reminder with that ID ({remind_id}).")
        return

    channel_id = job.kwargs.get("channel_id")
    channel_name = bot.get_channel(int(channel_id))
    message = job.kwargs.get("message")

    try:
        scheduler.remove_job(remind_id)
    except JobLookupError as e:
        await ctx.send(e)

    try:
        trigger_time = job.trigger.run_date
        msg = (
            f"**Removed** {remind_id}.\n"
            f"**Time**: {trigger_time.strftime('%Y-%m-%d %H:%M')} (in {countdown(remind_id)})\n"
            f"**Channel**: #{channel_name}\n"
            f"**Message**: {message}"
        )
    except AttributeError:
        msg = (
            f"**Removed** {remind_id}.\n"
            f"**Time**: Cronjob\n"
            f"**Channel**: #{channel_name}\n"
            f"**Message**: {message}"
        )

    await ctx.send(msg)


@slash.subcommand(
    base="remind",
    name="list",
    description="Show reminders.",
)
async def remind_list(ctx: SlashContext):

    # We use a embed to list the reminders.
    embed = discord.Embed(
        colour=discord.Colour.random(),
        title="discord-reminder-bot by TheLovinator#9276",
        description=f"Reminders for {ctx.guild.name}",
        url="https://github.com/TheLovinator1/discord-reminder-bot",
    )
    jobs = scheduler.get_jobs()
    for job in jobs:
        channel_id = job.kwargs.get("channel_id")
        channel_name = bot.get_channel(int(channel_id))

        # Only add reminders from channels in server we run "/reminder list" in
        for channel in ctx.guild.channels:
            if channel.id == channel_id:
                message = job.kwargs.get("message")
                try:
                    trigger_time = job.trigger.run_date
                    embed.add_field(
                        name=f"{message} in #{channel_name}",
                        value=f"{trigger_time.strftime('%Y-%m-%d %H:%M')} (in {countdown(job.id)})\nID: {job.id}",
                        inline=False,
                    )
                except AttributeError:
                    embed.add_field(
                        name=f"{message} in #{channel_name}",
                        value=f"Cronjob\nID: {job.id}",
                        inline=False,
                    )

    # The empty embed has 76 characters
    if len(embed) <= 76:
        msg = f"{ctx.guild.name} has no reminders."
        await ctx.send(msg)
    else:
        await ctx.send(embed=embed)


@slash.subcommand(
    base="remind",
    name="add",
    description="Set a reminder.",
    options=[
        create_option(
            name="message_reason",
            description="The message I'm going to send you.",
            option_type=SlashCommandOptionType.STRING,
            required=True,
        ),
        # TODO: Add support for dateparser.calendars.jalali and dateparser.calendars.hijri
        create_option(
            name="message_date",
            description="Time and/or date when you want to get reminded. Works only with the Gregorian calendar.",
            option_type=SlashCommandOptionType.STRING,
            required=True,
        ),
    ],
)
async def remind_add(ctx: SlashContext, message_date: str, message_reason: str):
    parsed_date = dateparser.parse(
        f"{message_date}",
        settings={
            "PREFER_DATES_FROM": "future",
            "TO_TIMEZONE": f"{config_timezone}",
        },
    )

    run_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
    reminder = scheduler.add_job(
        send_to_discord,
        run_date=run_date,
        kwargs={
            "channel_id": ctx.channel_id,
            "message": message_reason,
            "author_id": ctx.author_id,
        },
    )

    message = (
        f"Hello {ctx.author.display_name}, I will notify you at:\n"
        f"**{run_date}** (in {countdown(reminder.id)})\n"
        f"With the message:\n**{message_reason}**."
    )

    await ctx.send(message)


@slash.subcommand(
    base="remind",
    name="cron",
    description="Triggers when current time matches all specified time constraints, similarly to the UNIX cron.",
    options=[
        create_option(
            name="message_reason",
            description="The message I'm going to send you.",
            option_type=SlashCommandOptionType.STRING,
            required=True,
        ),
        create_option(
            name="year",
            description="4-digit year. (Example: 2042)",
            option_type=SlashCommandOptionType.STRING,
            required=False,
        ),
        create_option(
            name="month",
            description="Month (1-12)",
            option_type=SlashCommandOptionType.STRING,
            required=False,
        ),
        create_option(
            name="day",
            description="Day of month (1-31)",
            option_type=SlashCommandOptionType.STRING,
            required=False,
        ),
        create_option(
            name="week",
            description="ISO week (1-53)",
            option_type=SlashCommandOptionType.STRING,
            required=False,
        ),
        create_option(
            name="day_of_week",
            description="Number or name of weekday (0-6 or mon,tue,wed,thu,fri,sat,sun). The first weekday is monday.",
            option_type=SlashCommandOptionType.STRING,
            required=False,
        ),
        create_option(
            name="hour",
            description="Hour (0-23)",
            option_type=SlashCommandOptionType.STRING,
            required=False,
        ),
        create_option(
            name="minute",
            description="Minute (0-59)",
            option_type=SlashCommandOptionType.STRING,
            required=False,
        ),
        create_option(
            name="second",
            description="second (0-59)",
            option_type=SlashCommandOptionType.STRING,
            required=False,
        ),
        create_option(
            name="start_date",
            description="Earliest possible date/time to trigger on (inclusive)",
            option_type=SlashCommandOptionType.STRING,
            required=False,
        ),
        create_option(
            name="end_date",
            description="Latest possible date/time to trigger on (inclusive)",
            option_type=SlashCommandOptionType.STRING,
            required=False,
        ),
        create_option(
            name="timezone",
            description="Time zone to use for the date/time calculations (defaults to scheduler timezone)",
            option_type=SlashCommandOptionType.STRING,
            required=False,
        ),
        create_option(
            name="jitter",
            description="Delay the job execution by x seconds at most. Adds a random component to the execution time.",
            option_type=SlashCommandOptionType.INTEGER,
            required=False,
        ),
    ],
    # guild_ids=guild_ids,
)
async def remind_cron(
    ctx: SlashContext,
    message_reason: str,
    year=None,
    month=None,
    day=None,
    week=None,
    day_of_week=None,
    hour=None,
    minute=None,
    second=None,
    start_date=None,
    end_date=None,
    timezone=None,
    jitter=None,
):
    reminder = scheduler.add_job(
        send_to_discord,
        "cron",
        year=year,
        month=month,
        day=day,
        week=week,
        day_of_week=day_of_week,
        hour=hour,
        minute=minute,
        second=second,
        start_date=start_date,
        end_date=end_date,
        timezone=timezone,
        jitter=jitter,
        kwargs={
            "channel_id": ctx.channel_id,
            "message": message_reason,
            "author_id": ctx.author_id,
        },
    )

    message = (
        f"Hello {ctx.author.display_name}, first run in {countdown(reminder.id)}\n"
        f"With the message:\n**{message_reason}**."
        f"**Arguments**:\n"
    )

    options = [
        year,
        month,
        day,
        week,
        day_of_week,
        hour,
        minute,
        second,
        start_date,
        end_date,
        timezone,
        jitter,
    ]
    for option in options:
        if not None:
            message += f"**{option}**: {option}\n"

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
