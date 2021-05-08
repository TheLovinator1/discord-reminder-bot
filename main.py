import datetime
import logging
import os

import dateparser
import discord
import pytz
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from discord.errors import NotFound
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext
from discord_slash.error import IncorrectFormat, RequestFailure
from discord_slash.model import SlashCommandOptionType
from discord_slash.utils.manage_commands import create_choice, create_option
from dotenv import load_dotenv

bot = commands.Bot(
    command_prefix="!",
    description="Reminder bot for Discord by TheLovinator#9276",
    intents=discord.Intents.all(),  # TODO: Find the actual intents we need.
    # https://discordpy.readthedocs.io/en/latest/api.html#discord.Intents
)
slash = SlashCommand(bot, sync_commands=True)


def calc_countdown(remind_id: str) -> str:
    job = scheduler.get_job(remind_id)

    # Get_job() returns None when it can't find a job with that id.
    if type(job.trigger) is DateTrigger:
        trigger_time = job.trigger.run_date
    else:
        trigger_time = job.next_run_time

    if trigger_time is None:
        return "Failed to calculate time"

    # Get time and date the job will run and calculate how many days, hours and seconds.
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
async def on_slash_command_error(ctx, ex):
    logging.error(
        f'Error occurred during the execution of "/{ctx.name} {ctx.subcommand_name}" by {ctx.author}: {ex}'
    )
    if ex == RequestFailure:
        message = (f"Request to Discord API failed: {ex}",)
    elif ex == IncorrectFormat:
        message = (f"Incorrect format: {ex}",)
    elif ex == NotFound:
        message = (
            f"404 Not Found - I couldn't find the interaction or it took me longer than 3 seconds to respond: {ex}",
        )
    else:
        message = f"Error occurred during the execution of '/{ctx.name} {ctx.subcommand_name}': {ex}"

    await ctx.send(
        message + "\nIf this persists, please make an issue on "
        "[the GitHub repo](https://github.com/TheLovinator1/discord-reminder-bot/issues) or contact TheLovinator#9276",
        hidden=True,
    )


@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user.name}")


@slash.subcommand(
    base="remind",
    name="modify",
    description="Modify a reminder. Does not work with cron or interval.",
    options=[
        create_option(
            name="time_or_message",
            description="Choose between modifying the time or the message.",
            option_type=SlashCommandOptionType.STRING,
            required=True,
            choices=[
                create_choice(name="Date", value="date"),
                create_choice(name="Message", value="message"),
            ],
        ),
    ],
)
async def remind_modify(
    ctx: SlashContext,
    time_or_message: str,
):
    list_embed, jobs_dict = make_list(ctx, skip_cron_or_interval=True)

    # Modify first message we send to the user
    if time_or_message == "date":
        first_message = "the date"
    else:
        first_message = "the message"

    # The empty embed has 76 characters
    if len(list_embed) <= 76:
        await ctx.send(f"{ctx.guild.name} has no reminders.")
    else:
        await ctx.send(embed=list_embed)
        await ctx.channel.send(
            f"Type the corresponding number to the reminder were you wish to change {first_message}. "
            "Does not work with cron or interval. Type Exit to exit."
        )

        # Only check for response from the original user and in the correct channel
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            response_message = await bot.wait_for("message", check=check, timeout=60)
        except TimeoutError:
            return await ctx.channel.send("Timed out, try again.")
        if response_message.clean_content == "Exit":
            return await ctx.channel.send("Exited.")

        for num, job_from_dict in jobs_dict.items():
            if int(response_message.clean_content) == num:

                job = scheduler.get_job(job_from_dict)

                # Get_job() returns None when it can't find a job with that id.
                if job is None:
                    await ctx.send(f"No reminder with that ID ({job_from_dict}).")
                    return

                message = job.kwargs.get("message")
                the_final_countdown_old = calc_countdown(job.id)

                channel_name = bot.get_channel(int(job.kwargs.get("channel_id")))
                msg = f"**Modified** {job_from_dict} in #{channel_name}\n"
                if time_or_message == "message":
                    await ctx.channel.send("Type the new message. Type Exit to exit.")
                    try:
                        response_new_message = await bot.wait_for(
                            "message", check=check, timeout=60
                        )
                    except TimeoutError:
                        return await ctx.channel.send("Timed out, try again.")
                    if response_new_message.clean_content == "Exit":
                        return await ctx.channel.send("Exited.")

                    scheduler.modify_job(
                        job_from_dict,
                        kwargs={
                            "channel_id": job.kwargs.get("channel_id"),
                            "message": f"{response_new_message.clean_content}",
                            "author_id": job.kwargs.get("author_id"),
                        },
                    )
                    msg += f"**Old message**: {message}\n**New message**: {response_new_message.clean_content}\n"

                else:
                    await ctx.channel.send("Type the new date. Type Exit to exit.")
                    try:
                        response_new_date = await bot.wait_for(
                            "message", check=check, timeout=60
                        )
                    except TimeoutError:
                        return await ctx.channel.send("Timed out, try again.")
                    if response_new_date.clean_content == "Exit":
                        return await ctx.channel.send("Exited.")

                    parsed_date = dateparser.parse(
                        f"{response_new_date.clean_content}",
                        settings={
                            "PREFER_DATES_FROM": "future",
                            "TO_TIMEZONE": f"{config_timezone}",
                        },
                    )

                    remove_timezone_from_date = parsed_date.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

                    job = scheduler.reschedule_job(
                        job_from_dict, run_date=remove_timezone_from_date
                    )

                    remove_timezone_from_date_old = job.trigger.run_date.strftime(
                        "%Y-%m-%d %H:%M"
                    )
                    the_final_countdown_new = calc_countdown(job_from_dict)
                    msg += (
                        f"**Old date**: {remove_timezone_from_date_old} (in {the_final_countdown_old})\n"
                        f"**New date**: {remove_timezone_from_date} (in {the_final_countdown_new})"
                    )

                await ctx.send(msg)


@slash.subcommand(
    base="remind",
    name="remove",
    description="Remove a reminder.",
)
async def remind_remove(ctx: SlashContext):
    list_embed, jobs_dict = make_list(ctx)

    # The empty embed has 76 characters
    if len(list_embed) <= 76:
        await ctx.send(f"{ctx.guild.name} has no reminders.")
    else:
        await ctx.send(embed=list_embed)
        await ctx.channel.send(
            "Type the corresponding number to the reminder you wish to remove. Type Exit to exit."
        )

        # Only check for response from the original user and in the correct channel
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            response_message = await bot.wait_for("message", check=check, timeout=60)
        except TimeoutError:
            return await ctx.channel.send("Timed out, try again.")
        if response_message.clean_content == "Exit":
            return await ctx.channel.send("Exited.")

        for num, job_from_dict in jobs_dict.items():
            if int(response_message.clean_content) == num:
                job = scheduler.get_job(job_from_dict)
                if job is None:
                    await ctx.channel.send(
                        f"No reminder with that ID ({job_from_dict})."
                    )
                    return

                channel_id = job.kwargs.get("channel_id")
                channel_name = bot.get_channel(int(channel_id))
                message = job.kwargs.get("message")

                # Only normal reminders have trigger.run_date, cron and interval has next_run_time
                if type(job.trigger) is DateTrigger:
                    trigger_time = job.trigger.run_date
                else:
                    trigger_time = job.next_run_time

                # Paused reminders returns None
                if trigger_time is None:
                    trigger_value = "Paused - can be resumed with '/remind resume'"
                else:
                    trigger_value = f'{trigger_time.strftime("%Y-%m-%d %H:%M")} (in {calc_countdown(job.id)})'

                msg = (
                    f"**Removed** {message} in #{channel_name}.\n"
                    f"**Time**: {trigger_value}"
                )

                scheduler.remove_job(job_from_dict)

                await ctx.channel.send(msg)


def make_list(ctx, skip_datetriggers=False, skip_cron_or_interval=False):
    jobs_dict = {}
    job_number = 0
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
                job_number += 1
                jobs_dict[job_number] = job.id
                message = job.kwargs.get("message")

                # Only normal reminders have trigger.run_date, cron and interval has next_run_time
                if type(job.trigger) is DateTrigger:
                    trigger_time = job.trigger.run_date
                    if skip_datetriggers:
                        continue
                else:
                    trigger_time = job.next_run_time
                    if skip_cron_or_interval:
                        continue

                # Paused reminders returns None
                if trigger_time is None:
                    trigger_value = "Paused - can be resumed with '/remind resume'"
                else:
                    trigger_value = f'{trigger_time.strftime("%Y-%m-%d %H:%M")} (in {calc_countdown(job.id)})'

                embed.add_field(
                    name=f"{job_number}) {message} in #{channel_name}",
                    value=f"{trigger_value}",
                    inline=False,
                )
    return embed, jobs_dict


@slash.subcommand(
    base="remind",
    name="list",
    description="Show reminders.",
)
async def remind_list(ctx: SlashContext):
    list_embed, jobs_dict = make_list(ctx)

    # The empty embed has 76 characters
    if len(list_embed) <= 76:
        await ctx.send(f"{ctx.guild.name} has no reminders.")
    else:
        await ctx.send(embed=list_embed)


@slash.subcommand(
    base="remind",
    name="pause",
    description="Pause reminder. For cron or interval.",
)
async def remind_pause(ctx: SlashContext):
    list_embed, jobs_dict = make_list(ctx, skip_datetriggers=True)

    # The empty embed has 76 characters
    if len(list_embed) <= 76:
        await ctx.send(f"{ctx.guild.name} has no reminders.")
    else:
        await ctx.send(embed=list_embed)
        await ctx.channel.send(
            "Type the corresponding number to the reminder you wish to pause. Type Exit to exit."
        )

        # Only check for response from the original user and in the correct channel
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            response_reminder = await bot.wait_for("message", check=check, timeout=60)
        except TimeoutError:
            return await ctx.channel.send("Timed out, try again.")
        if response_reminder.clean_content == "Exit":
            return await ctx.channel.send("Exited.")

        for num, job_from_dict in jobs_dict.items():
            if int(response_reminder.clean_content) == num:
                job = scheduler.get_job(job_from_dict)
                channel_id = job.kwargs.get("channel_id")
                channel_name = bot.get_channel(int(channel_id))
                message = job.kwargs.get("message")

                # Only normal reminders have trigger.run_date, cron and interval has next_run_time
                if type(job.trigger) is DateTrigger:
                    trigger_time = job.trigger.run_date
                else:
                    trigger_time = job.next_run_time

                # Paused reminders returns None
                if trigger_time is None:
                    return await ctx.channel.send(
                        f"{response_reminder.clean_content} | {message} in #{channel_name} is already paused."
                    )
                else:
                    trigger_value = f'{trigger_time.strftime("%Y-%m-%d %H:%M")} (in {calc_countdown(job.id)})'

                msg = (
                    f"**Paused** {message} in #{channel_name}.\n"
                    f"**Time**: {trigger_value}"
                )

                scheduler.pause_job(job_from_dict)

                await ctx.channel.send(msg)


@slash.subcommand(
    base="remind",
    name="resume",
    description="Resume paused reminder. For cron or interval.",
)
async def remind_resume(ctx: SlashContext):
    list_embed, jobs_dict = make_list(ctx, skip_datetriggers=True)

    # The empty embed has 76 characters
    if len(list_embed) <= 76:
        await ctx.send(f"{ctx.guild.name} has no reminders.")
    else:
        await ctx.send(embed=list_embed)
        await ctx.channel.send(
            "Type the corresponding number to the reminder you wish to pause. Type Exit to exit."
        )

        # Only check for response from the original user and in the correct channel
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            response_message = await bot.wait_for("message", check=check, timeout=60)
        except TimeoutError:
            return await ctx.channel.send("Timed out, try again.")
        if response_message.clean_content == "Exit":
            return await ctx.channel.send("Exited.")

        for num, job_from_dict in jobs_dict.items():
            if int(response_message.clean_content) == num:
                job = scheduler.get_job(job_from_dict)
                if job is None:
                    await ctx.send(f"No reminder with that ID ({job_from_dict}).")
                    return

                channel_id = job.kwargs.get("channel_id")
                channel_name = bot.get_channel(int(channel_id))
                message = job.kwargs.get("message")

                try:
                    scheduler.resume_job(job_from_dict)
                except Exception as e:
                    await ctx.send(e)

                # Only normal reminders have trigger.run_date, cron and interval has next_run_time
                if type(job.trigger) is DateTrigger:
                    trigger_time = job.trigger.run_date
                else:
                    trigger_time = job.next_run_time

                # Paused reminders returns None
                if trigger_time is None:
                    trigger_value = "Paused - can be resumed with '/remind resume'"
                else:
                    trigger_value = f'{trigger_time.strftime("%Y-%m-%d %H:%M")} (in {calc_countdown(job.id)})'

                msg = (
                    f"**Resumed** {message} in #{channel_name}.\n"
                    f"**Time**: {trigger_value}\n"
                )

                await ctx.send(msg)


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
        f"**{run_date}** (in {calc_countdown(reminder.id)})\n"
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
            description="Second (0-59)",
            option_type=SlashCommandOptionType.STRING,
            required=False,
        ),
        create_option(
            name="start_date",
            description="Earliest possible time to trigger on, in the ISO 8601 format. (Example: 2010-10-10 09:30:00)",
            option_type=SlashCommandOptionType.STRING,
            required=False,
        ),
        create_option(
            name="end_date",
            description="Latest possible time to trigger on, in the ISO 8601 format. (Example: 2010-10-10 09:30:00)",
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
    job = scheduler.add_job(
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

    # TODO: Add arguments
    message = (
        f"Hello {ctx.author.display_name}, first run in {calc_countdown(job.id)}\n"
        f"With the message:\n**{message_reason}**."
    )

    await ctx.send(message)


@slash.subcommand(
    base="remind",
    name="interval",
    description="Schedules messages to be run periodically, on selected intervals.",
    options=[
        create_option(
            name="message_reason",
            description="The message I'm going to send you.",
            option_type=SlashCommandOptionType.STRING,
            required=True,
        ),
        create_option(
            name="weeks",
            description="Number of weeks to wait",
            option_type=SlashCommandOptionType.INTEGER,
            required=False,
        ),
        create_option(
            name="days",
            description="Number of days to wait",
            option_type=SlashCommandOptionType.INTEGER,
            required=False,
        ),
        create_option(
            name="hours",
            description="Number of hours to wait",
            option_type=SlashCommandOptionType.INTEGER,
            required=False,
        ),
        create_option(
            name="minutes",
            description="Number of minutes to wait",
            option_type=SlashCommandOptionType.INTEGER,
            required=False,
        ),
        create_option(
            name="seconds",
            description="Number of seconds to wait.",
            option_type=SlashCommandOptionType.INTEGER,
            required=False,
        ),
        create_option(
            name="start_date",
            description="When to start, in the ISO 8601 format. (Example: 2010-10-10 09:30:00)",
            option_type=SlashCommandOptionType.STRING,
            required=False,
        ),
        create_option(
            name="end_date",
            description="When to stop, in the ISO 8601 format. (Example: 2014-06-15 11:00:00)",
            option_type=SlashCommandOptionType.STRING,
            required=False,
        ),
        create_option(
            name="timezone",
            description="Time zone to use for the date/time calculations",
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
)
async def remind_interval(
    ctx: SlashContext,
    message_reason: str,
    weeks=0,
    days=0,
    hours=0,
    minutes=0,
    seconds=0,
    start_date=None,
    end_date=None,
    timezone=None,
    jitter=None,
):
    job = scheduler.add_job(
        send_to_discord,
        "interval",
        weeks=weeks,
        days=days,
        hours=hours,
        minutes=minutes,
        seconds=seconds,
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

    # TODO: Add arguments
    message = (
        f"Hello {ctx.author.display_name}, first run in {calc_countdown(job.id)}\n"
        f"With the message:\n**{message_reason}**."
    )

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
