import datetime
import logging

import dateparser
import discord
import pytz
from apscheduler.triggers.date import DateTrigger
from discord.errors import NotFound
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext
from discord_slash.error import IncorrectFormat, RequestFailure
from discord_slash.model import SlashCommandOptionType
from discord_slash.utils.manage_commands import create_choice, create_option

from discord_reminder_bot.settings import bot_token, config_timezone, log_level, scheduler, sqlite_location

bot = commands.Bot(
    command_prefix="!", description="Reminder bot for Discord by TheLovinator#9276", intents=discord.Intents.all()
)
slash = SlashCommand(bot, sync_commands=True)


def calc_countdown(job) -> str:
    """Get trigger time from a reminder and calculate how many days, hours and minutes till trigger.

    Days/Minutes will not be included if 0.

    Args:
        job ([type]): The job. Can be cron, interval or normal. #TODO: Find type

    Returns:
        str: Returns days, hours and minutes till reminder. Returns "Failed to calculate time" if no job is found.
    """
    if type(job.trigger) is DateTrigger:
        trigger_time = job.trigger.run_date
    else:
        trigger_time = job.next_run_time

    # Get_job() returns None when it can't find a job with that id.
    if trigger_time is None:
        return "Failed to calculate time"

    # Get time and date the job will run and calculate how many days, hours and seconds.
    countdown = trigger_time - datetime.datetime.now(tz=pytz.timezone(config_timezone))

    days, hours, minutes = (
        countdown.days,
        countdown.seconds // 3600,
        countdown.seconds // 60 % 60,
    )
    return ", ".join(
        f"{x} {y}{'s'*(x!=1)}"
        for x, y in (
            (days, "day"),
            (hours, "hour"),
            (minutes, "minute"),
        )
        if x
    )


@bot.event
async def on_slash_command_error(ctx: SlashContext, ex: Exception):
    """Send message to Discord when slash command fails.

    Args:
        ctx (SlashContext): Context. The meta data about the slash command.
        ex (Exception): Exception that raised.

    https://discord-py-slash-command.readthedocs.io/en/latest/discord_slash.error.html
    """
    logging.error(f'Error occurred during the execution of "/{ctx.name} {ctx.subcommand_name}" by {ctx.author}: {ex}')
    if ex == RequestFailure:
        message = f"Request to Discord API failed: {ex}"
    elif ex == IncorrectFormat:
        message = f"Incorrect format: {ex}"
    elif ex == NotFound:
        message = f"I couldn't find the interaction or it took me longer than 3 seconds to respond: {ex}"
    else:
        message = f"Error occurred during the execution of '/{ctx.name} {ctx.subcommand_name}': {ex}"

    await ctx.send(
        f"{message}\nIf this persists, please make an issue on "
        "[the GitHub repo](https://github.com/TheLovinator1/discord-reminder-bot/issues) or contact TheLovinator#9276",
        hidden=True,
    )


@bot.event
async def on_ready():
    """Log our bots username on start."""
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
async def command_modify(ctx: SlashContext, time_or_message: str):
    """Modify a reminder. You can change time or message.

    Args:
        ctx (SlashContext): Context. The meta data about the slash command.
        time_or_message (str): Choose between modifying the message or time.

    Returns:
        [type]: Send message to Discord.
    """
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
                the_final_countdown_old = calc_countdown(job)

                channel_name = bot.get_channel(int(job.kwargs.get("channel_id")))
                msg = f"**Modified** {job_from_dict} in #{channel_name}\n"
                if time_or_message == "message":
                    await ctx.channel.send("Type the new message. Type Exit to exit.")
                    try:
                        response_new_message = await bot.wait_for("message", check=check, timeout=60)
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
                        response_new_date = await bot.wait_for("message", check=check, timeout=60)
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
                    # FIXME: Fix mypy error
                    remove_timezone_from_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")  # type: ignore[union-attr]

                    job = scheduler.reschedule_job(job_from_dict, run_date=remove_timezone_from_date)

                    remove_timezone_from_date_old = job.trigger.run_date.strftime("%Y-%m-%d %H:%M")
                    the_final_countdown_new = calc_countdown(job_from_dict)
                    msg += (
                        f"**Old date**: {remove_timezone_from_date_old} (in {the_final_countdown_old})\n"
                        f"**New date**: {remove_timezone_from_date} (in {the_final_countdown_new})"
                    )

                await ctx.send(msg)


@slash.subcommand(base="remind", name="remove", description="Remove a reminder.")
async def remind_remove(ctx: SlashContext):
    """Select reminder from list that you want to remove.

    Args:
        ctx (SlashContext): Context. The meta data about the slash command.

    Returns:
        [type]: Send message to Discord.
    """
    list_embed, jobs_dict = make_list(ctx)

    # The empty embed has 76 characters
    if len(list_embed) <= 76:
        await ctx.send(f"{ctx.guild.name} has no reminders.")
    else:
        await ctx.send(embed=list_embed)
        await ctx.channel.send("Type the corresponding number to the reminder you wish to remove. Type Exit to exit.")

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
                    await ctx.channel.send(f"No reminder with that ID ({job_from_dict}).")
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
                    trigger_value = f'{trigger_time.strftime("%Y-%m-%d %H:%M")} (in {calc_countdown(job)})'

                msg = f"**Removed** {message} in #{channel_name}.\n**Time**: {trigger_value}"

                scheduler.remove_job(job_from_dict)

                await ctx.channel.send(msg)


def make_list(ctx, skip_datetriggers=False, skip_cron_or_interval=False):
    """Create a list of reminders.

    Args:
        ctx (SlashContext): Context. The meta data about the slash command.
        skip_datetriggers (bool, optional): Only show cron jobs and interval reminders. Defaults to False.
        skip_cron_or_interval (bool, optional): Only show normal reminders. Defaults to False.

    Returns:
        embed: Embed is the list of reminders that we send to Discord.
        jobs_dict: Dictionary that contains placement in list and job id.
    """
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
                    trigger_value = f'{trigger_time.strftime("%Y-%m-%d %H:%M")} (in {calc_countdown(job)})'

                # Max length is 256
                field_name = f"{job_number}) {message} in #{channel_name}"
                field_name = field_name[:253] + (field_name[253:] and "...")

                # Max length is 1024
                field_value = f"{trigger_value}"
                field_value = field_value[:1021] + (field_value[1021:] and "...")

                embed.add_field(
                    name=field_name,
                    value=field_value,
                    inline=False,
                )
    return embed, jobs_dict


@slash.subcommand(
    base="remind",
    name="list",
    description="Show reminders.",
)
async def remind_list(ctx: SlashContext):
    """Send a list of reminders to Discord.

    Args:
        ctx (SlashContext): Context. The meta data about the slash command.
    """
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
    """Get a list of reminders that you can pause.

    Args:
        ctx (SlashContext): Context. The meta data about the slash command.

    Returns:
        [type]: Sends message to Discord.
    """
    list_embed, jobs_dict = make_list(ctx, skip_datetriggers=True)

    # The empty embed has 76 characters
    if len(list_embed) <= 76:
        await ctx.send(f"{ctx.guild.name} has no reminders.")
    else:
        await ctx.send(embed=list_embed)
        await ctx.channel.send("Type the corresponding number to the reminder you wish to pause. Type Exit to exit.")

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
                    trigger_value = f'{trigger_time.strftime("%Y-%m-%d %H:%M")} (in {calc_countdown(job)})'

                msg = f"**Paused** {message} in #{channel_name}.\n**Time**: {trigger_value}"

                scheduler.pause_job(job_from_dict)

                await ctx.channel.send(msg)


@slash.subcommand(
    base="remind",
    name="resume",
    description="Resume paused reminder. For cron or interval.",
)
async def remind_resume(ctx: SlashContext):
    """Send a list of reminders to pause to Discord.

    Args:
        ctx (SlashContext): Context. The meta data about the slash command.

    Returns:
        [type]: Sends message to Discord.
    """
    list_embed, jobs_dict = make_list(ctx, skip_datetriggers=True)

    # The empty embed has 76 characters
    if len(list_embed) <= 76:
        await ctx.send(f"{ctx.guild.name} has no reminders.")
    else:
        await ctx.send(embed=list_embed)
        await ctx.channel.send("Type the corresponding number to the reminder you wish to pause. Type Exit to exit.")

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
                    trigger_value = f'{trigger_time.strftime("%Y-%m-%d %H:%M")} (in {calc_countdown(job)})'

                msg = f"**Resumed** {message} in #{channel_name}.\n**Time**: {trigger_value}\n"

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
        create_option(
            name="message_date",
            description="Time and/or date when you want to get reminded. Works only with the Gregorian calendar.",
            option_type=SlashCommandOptionType.STRING,
            required=True,
        ),
    ],
)
async def remind_add(ctx: SlashContext, message_date: str, message_reason: str):
    """Add a new reminder. You can add a date and message.

    Args:
        ctx (SlashContext): Context. The meta data about the slash command.
        message_date (str): The date or time that will get parsed.
        message_reason (str): The message the bot should write when the reminder is triggered.
    """
    parsed_date = dateparser.parse(
        f"{message_date}",
        settings={
            "PREFER_DATES_FROM": "future",
            "TO_TIMEZONE": f"{config_timezone}",
        },
    )
    # FIXME: Fix mypy error
    run_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S")  # type: ignore[union-attr]
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
        f"**{run_date}** (in {calc_countdown(reminder)})\n"
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
    year: int = None,
    month: int = None,
    day: int = None,
    week: int = None,
    day_of_week: str = None,
    hour: int = None,
    minute: int = None,
    second: int = None,
    start_date: str = None,
    end_date: str = None,
    timezone: str = None,
    jitter: int = None,
):
    """Create new cron job. Works like UNIX cron.

    https://en.wikipedia.org/wiki/Cron
    Args that are None will be defaulted to *.

    Args:
        ctx (SlashContext): Context. The meta data about the slash command.
        message_reason (str): The message the bot should send everytime cron job triggers.
        year (int, optional): 4-digit year. Defaults to None.
        month (int, optional): Month (1-12). Defaults to None.
        day (int, optional): Day of month (1-31). Defaults to None.
        week (int, optional): ISO week (1-53). Defaults to None.
        day_of_week (str, optional): Number or name of weekday (0-6 or mon,tue,wed,thu,fri,sat,sun). Defaults to None.
        hour (int, optional): Hour (0-23). Defaults to None.
        minute (int, optional): Minute (0-59). Defaults to None.
        second (int, optional): Second (0-59). Defaults to None.
        start_date (str, optional): Earliest possible date/time to trigger on (inclusive). Defaults to None.
        end_date (str, optional): Latest possible date/time to trigger on (inclusive). Defaults to None.
        timezone (str, optional): Time zone to use for the date/time calculations Defaults to scheduler timezone.
        jitter (int, optional): Delay the job execution by jitter seconds at most. Defaults to None.

        https://apscheduler.readthedocs.io/en/stable/modules/triggers/cron.html#module-apscheduler.triggers.cron
    """
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
        f"Hello {ctx.author.display_name}, first run in {calc_countdown(job)}\n"
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
    weeks: int = 0,
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    seconds: int = 0,
    start_date: str = None,
    end_date: str = None,
    timezone: str = None,
    jitter: int = None,
):
    """Create new reminder that triggers based on a interval.

    Args:
        ctx (SlashContext): Context. The meta data about the slash command.
        message_reason (str): The message we should write when triggered.
        weeks (int, optional): Number of weeks to wait. Defaults to 0.
        days (int, optional): Number of days to wait. Defaults to 0.
        hours (int, optional): Number of hours to wait. Defaults to 0.
        minutes (int, optional): Number of minutes to wait. Defaults to 0.
        seconds (int, optional): Number of seconds to wait. Defaults to 0.
        start_date (str, optional): Starting point for the interval calculation. Defaults to None.
        end_date (str, optional): Latest possible date/time to trigger on. Defaults to None.
        timezone (str, optional): Time zone to use for the date/time calculations. Defaults to None.
        jitter (int, optional): Delay the job execution by jitter seconds at most. Defaults to None.
    """
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
        f"Hello {ctx.author.display_name}, first run in {calc_countdown(job)}\n"
        f"With the message:\n**{message_reason}**."
    )

    await ctx.send(message)


async def send_to_discord(channel_id: int, message: str, author_id: int):
    """Send a message to Discord.

    Args:
        channel_id (int): The Discord channel ID.
        message (str): The message.
        author_id (int): User we should ping.
    """
    # TODO: Check if channel exists.
    channel = bot.get_channel(int(channel_id))
    await channel.send(f"<@{author_id}>\n{message}")


def start():
    """Start scheduler and log in to Discord."""
    logging.basicConfig(level=logging.getLevelName(log_level))
    logging.info(
        f"\nsqlite_location = {sqlite_location}\n"
        f"config_timezone = {config_timezone}\n"
        f"bot_token = {bot_token}\n"
        f"log_level = {log_level}"
    )

    scheduler.start()
    bot.run(bot_token)


if __name__ == "__main__":
    start()
