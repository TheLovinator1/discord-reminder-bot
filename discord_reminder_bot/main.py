from __future__ import annotations

import datetime
import json
import os
import platform
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import dateparser
import discord
import pytz
import sentry_sdk
from apscheduler import events
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED, JobExecutionEvent
from apscheduler.job import Job
from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from discord.abc import PrivateChannel
from discord_webhook import DiscordWebhook
from dotenv import load_dotenv
from loguru import logger

from interactions.api.models.misc import Snowflake

if TYPE_CHECKING:
    from discord.guild import GuildChannel
    from discord.interactions import InteractionChannel
    from discord.types.channel import _BaseChannel
    from requests import Response


load_dotenv()

default_sentry_dsn: str = "https://c4c61a52838be9b5042144420fba5aaa@o4505228040339456.ingest.us.sentry.io/4508707268984832"
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN", default_sentry_dsn),
    environment=platform.node() or "Unknown",
    traces_sample_rate=1.0,
    send_default_pii=True,
)


def generate_markdown_state(state: dict[str, Any]) -> str:
    """Format the __getstate__ dictionary for Discord markdown.

    Args:
        state (dict): The __getstate__ dictionary.

    Returns:
        str: The formatted string.
    """
    if not state:
        return "```json\nNo state found.\n```"

    # discord.app_commands.errors.CommandInvokeError: Command 'remove' raised an exception: TypeError: Object of type IntervalTrigger is not JSON serializable

    # Convert the IntervalTrigger to a string representation
    for key, value in state.items():
        if isinstance(value, IntervalTrigger):
            state[key] = "IntervalTrigger"
        elif isinstance(value, DateTrigger):
            state[key] = "DateTrigger"
        elif isinstance(value, Job):
            state[key] = "Job"
        elif isinstance(value, Snowflake):
            state[key] = str(value)

    try:
        msg: str = json.dumps(state, indent=4, default=str)
    except TypeError as e:
        e.add_note("This is likely due to a non-serializable object in the state. Please check the state for any non-serializable objects.")
        e.add_note(f"{state=}")
        logger.error(f"Failed to serialize state: {e}")
        return "```json\nFailed to serialize state.\n```"

    return "```json\n" + msg + "\n```"


def parse_time(date_to_parse: str | None, timezone: str | None = os.getenv("TIMEZONE")) -> datetime.datetime | None:
    """Parse a date string into a datetime object.

    Args:
        date_to_parse(str): The date string to parse.
        timezone(str, optional): The timezone to use. Defaults to the TIMEZONE environment variable.

    Returns:
        datetime.datetime: The parsed datetime object.
    """
    if not date_to_parse:
        logger.error("No date provided to parse.")
        return None

    if not timezone:
        logger.error("No timezone provided to parse date.")
        return None

    logger.info(f"Parsing date: '{date_to_parse}' with timezone: '{timezone}'")

    try:
        parsed_date: datetime.datetime | None = dateparser.parse(
            date_string=date_to_parse,
            settings={
                "PREFER_DATES_FROM": "future",
                "TIMEZONE": f"{timezone}",
                "RETURN_AS_TIMEZONE_AWARE": True,
                "RELATIVE_BASE": datetime.datetime.now(tz=ZoneInfo(str(timezone))),
            },
        )
    except (ValueError, TypeError) as e:
        logger.error(f"Failed to parse date: '{date_to_parse}' with timezone: '{timezone}'. Error: {e}")
        return None

    logger.debug(f"Parsed date: {parsed_date} from '{date_to_parse}'")

    return parsed_date


def calculate(job: Job) -> str:
    """Calculate the time left for a job.

    Args:
        job: The job to calculate the time for.

    Returns:
        str: The time left for the job or "Paused" if the job is paused or has no next run time.
    """
    trigger_time = None
    if isinstance(job.trigger, DateTrigger | IntervalTrigger):
        trigger_time = job.next_run_time or None

    elif isinstance(job.trigger, CronTrigger):
        if not job.next_run_time:
            logger.debug(f"No next run time found for '{job.id}', probably paused? {job.__getstate__()}")
            return "Paused"

        trigger_time = job.trigger.get_next_fire_time(None, datetime.datetime.now(tz=job._scheduler.timezone))  # noqa: SLF001

    logger.debug(f"{type(job.trigger)=}, {trigger_time=}")

    if not trigger_time:
        logger.debug("No trigger time found")
        return "Paused"

    return f"<t:{int(trigger_time.timestamp())}:R>"


def get_human_readable_time(job: Job) -> str:
    """Get the human-readable time for a job.

    Args:
        job: The job to get the time for.

    Returns:
        str: The human-readable time.
    """
    trigger_time = None
    if isinstance(job.trigger, DateTrigger | IntervalTrigger):
        trigger_time = job.next_run_time or None

    elif isinstance(job.trigger, CronTrigger):
        if not job.next_run_time:
            logger.debug(f"No next run time found for '{job.id}', probably paused? {job.__getstate__()}")
            return "Paused"

        trigger_time = job.trigger.get_next_fire_time(None, datetime.datetime.now(tz=job._scheduler.timezone))  # noqa: SLF001

    if not trigger_time:
        logger.debug("No trigger time found")
        return "Paused"

    return trigger_time.strftime("%Y-%m-%d %H:%M:%S")


@lru_cache(maxsize=1)
def get_scheduler() -> AsyncIOScheduler:
    """Return the scheduler instance.

    Uses the SQLITE_LOCATION environment variable for the SQLite database location.

    Raises:
        ValueError: If the timezone is missing or invalid.

    Returns:
        AsyncIOScheduler: The scheduler instance.
    """
    config_timezone: str | None = os.getenv("TIMEZONE")
    if not config_timezone:
        msg = "Missing timezone. Please set the TIMEZONE environment variable."
        raise ValueError(msg)

    # Test if the timezone is valid
    try:
        ZoneInfo(config_timezone)
    except (ZoneInfoNotFoundError, ModuleNotFoundError) as e:
        msg: str = f"Invalid timezone: {config_timezone}. Error: {e}"
        raise ValueError(msg) from e

    sqlite_location: str = os.getenv("SQLITE_LOCATION", default="/jobs.sqlite")
    logger.info(f"Using SQLite database at: {sqlite_location}")

    jobstores: dict[str, SQLAlchemyJobStore] = {"default": SQLAlchemyJobStore(url=f"sqlite://{sqlite_location}")}
    job_defaults: dict[str, bool] = {"coalesce": True}
    timezone = pytz.timezone(config_timezone)
    return AsyncIOScheduler(jobstores=jobstores, timezone=timezone, job_defaults=job_defaults)


scheduler: AsyncIOScheduler = get_scheduler()


def my_listener(event: JobExecutionEvent) -> None:
    """Listener for job events.

    Args:
        event: The event that occurred.
    """
    if event.code == events.EVENT_JOB_MISSED:
        scheduled_time: str = event.scheduled_run_time.strftime("%Y-%m-%d %H:%M:%S")
        msg: str = f"Job {event.job_id} was missed! Was scheduled at {scheduled_time}"
        send_webhook(message=msg)

    if event.exception:
        with sentry_sdk.push_scope() as scope:
            scope.set_extra("job_id", event.job_id)
            scope.set_extra("scheduled_run_time", event.scheduled_run_time.isoformat() if event.scheduled_run_time else "None")
            scope.set_extra("event_code", event.code)
            sentry_sdk.capture_exception(event.exception)

        send_webhook(f"discord-reminder-bot failed to send message to Discord\n{event}")


class RemindBotClient(discord.Client):
    """The bot client for the Discord Reminder Bot."""

    def __init__(self, *, intents: discord.Intents) -> None:
        """Initialize the bot client and command tree.

        Args:
            intents: The intents to use.
        """
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)

    async def on_error(self, event_method: str, *args: list[Any], **kwargs: dict[str, Any]) -> None:
        """Log errors that occur in the bot."""
        # Log the error
        logger.exception(f"An error occurred in {event_method} with args: {args} and kwargs: {kwargs}")

        # Add context to Sentry
        with sentry_sdk.push_scope() as scope:
            # Add event details
            scope.set_tag("event_method", event_method)
            scope.set_extra("args", args)
            scope.set_extra("kwargs", kwargs)

            # Add bot state
            scope.set_tag("bot_user_id", self.user.id if self.user else "Unknown")
            scope.set_tag("bot_user_name", str(self.user) if self.user else "Unknown")
            scope.set_tag("bot_latency", self.latency)

            # If specific arguments are available, extract and add details
            if args:
                interaction = next((arg for arg in args if isinstance(arg, discord.Interaction)), None)
                if interaction:
                    scope.set_extra("interaction_id", interaction.id)
                    scope.set_extra("interaction_user", interaction.user.id)
                    scope.set_extra("interaction_user_tag", str(interaction.user))
                    scope.set_extra("interaction_command", interaction.command.name if interaction.command else None)
                    scope.set_extra("interaction_channel", str(interaction.channel))
                    scope.set_extra("interaction_guild", str(interaction.guild) if interaction.guild else None)

                    # Add Sentry tags for interaction details
                    scope.set_tag("interaction_id", interaction.id)
                    scope.set_tag("interaction_user_id", interaction.user.id)
                    scope.set_tag("interaction_user_tag", str(interaction.user))
                    scope.set_tag("interaction_command", interaction.command.name if interaction.command else "None")
                    scope.set_tag("interaction_channel_id", interaction.channel.id if interaction.channel else "None")
                    scope.set_tag("interaction_channel_name", str(interaction.channel))
                    scope.set_tag("interaction_guild_id", interaction.guild.id if interaction.guild else "None")
                    scope.set_tag("interaction_guild_name", str(interaction.guild) if interaction.guild else "None")

            # Add APScheduler context
            scope.set_extra("scheduler_jobs", [job.id for job in scheduler.get_jobs()])

            sentry_sdk.capture_exception()

    async def on_ready(self) -> None:
        """Log when the bot is ready."""
        logger.info(f"Logged in as {self.user} ({self.user.id if self.user else 'Unknown'})")

    async def setup_hook(self) -> None:
        """Setup the bot."""
        scheduler.start()
        scheduler.add_listener(my_listener, EVENT_JOB_MISSED | EVENT_JOB_ERROR)
        jobs: list[Job] = scheduler.get_jobs()
        if not jobs:
            logger.info("No jobs available.")
            return

        logger.info("Jobs available:")
        try:
            for job in jobs:
                msg: str = job.kwargs.get("message", "") if (job.kwargs and isinstance(job.kwargs, dict)) else ""
                time: str = "Paused"
                if hasattr(job, "next_run_time") and job.next_run_time and isinstance(job.next_run_time, datetime.datetime):
                    time = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"\t{job.id}: {job.name} - {time} - {msg}")

        except (AttributeError, LookupError):
            logger.exception("Failed to loop through jobs")

        await self.tree.sync()


def generate_reminder_summary(ctx: discord.Interaction) -> list[str]:  # noqa: PLR0912
    """Create a message with all the jobs, splitting messages into chunks of up to 2000 characters.

    Args:
        ctx (discord.Interaction): The context of the interaction.

    Returns:
        list[str]: A list of messages with all the jobs.
    """
    jobs: list[Job] = scheduler.get_jobs()
    msgs: list[str] = []

    guild: discord.Guild | None = None
    if isinstance(ctx.channel, discord.abc.GuildChannel):
        guild = ctx.channel.guild

    channels: list[GuildChannel] | list[_BaseChannel] = list(guild.channels) if guild else []
    channels_in_this_guild: list[int] = [c.id for c in channels]
    jobs_in_guild: list[Job] = []
    for job in jobs:
        guild_id: int = guild.id if guild else -1

        guild_id_from_kwargs = int(job.kwargs.get("guild_id", 0))

        if guild_id_from_kwargs and guild_id_from_kwargs != guild_id:
            logger.debug(f"Skipping job: {job.id} because it's not in the current guild.")
            continue

        if job.kwargs.get("channel_id") not in channels_in_this_guild:
            logger.debug(f"Skipping job: {job.id} because it's not in the current guild.")
            continue

        logger.debug(f"Adding job: {job.id} to the list.")
        jobs_in_guild.append(job)

    if len(jobs) != len(jobs_in_guild):
        logger.info(f"Filtered out {len(jobs) - len(jobs_in_guild)} jobs that are not in the current guild.")

    jobs = jobs_in_guild

    if not jobs:
        return ["No scheduled jobs found in the database."]

    header = (
        "You can use the following commands to manage reminders:\n"
        "Only jobs in the current guild are shown.\n"
        "`/remind pause <job_id>` - Pause a reminder\n"
        "`/remind unpause <job_id>` - Unpause a reminder\n"
        "`/remind remove <job_id>` - Remove a reminder\n"
        "`/remind modify <job_id>` - Modify the time of a reminder\n"
        "List of all reminders:\n"
    )

    current_msg: str = header

    for job in jobs:
        # Build job-specific message
        job_msg: str = "```md\n"
        job_msg += f"# {job.kwargs.get('message', '')}\n"
        job_msg += f"   * {job.id}\n"
        job_msg += f"   * {job.trigger} {get_human_readable_time(job)}"

        if job.kwargs.get("user_id"):
            job_msg += f" <@{job.kwargs.get('user_id')}>"
        if job.kwargs.get("channel_id"):
            channel = bot.get_channel(job.kwargs.get("channel_id"))
            if channel and isinstance(channel, discord.abc.GuildChannel | discord.Thread):
                job_msg += f" in #{channel.name}"

        if job.kwargs.get("guild_id"):
            guild = bot.get_guild(job.kwargs.get("guild_id"))
            if guild:
                job_msg += f" in {guild.name}"
            job_msg += f" {job.kwargs.get('guild_id')}"

        job_msg += "```"

        # If adding this job exceeds 2000 characters, push the current message and start a new one.
        if len(current_msg) + len(job_msg) > 2000:
            msgs.append(current_msg)
            current_msg = job_msg
        else:
            current_msg += job_msg

    # Append any remaining content in current_msg.
    if current_msg:
        msgs.append(current_msg)

    return msgs


class RemindGroup(discord.app_commands.Group):
    """Base class for the /remind commands."""

    def __init__(self) -> None:
        """Initialize the remind group."""
        super().__init__(name="remind", description="Group for remind commands")
        """Group for remind commands."""

    # /remind add
    @discord.app_commands.command(name="add", description="Add a new reminder")
    async def add(
        self,
        interaction: discord.Interaction,
        message: str,
        time: str,
        channel: discord.TextChannel | None = None,
        user: discord.User | None = None,
        dm_and_current_channel: bool | None = None,
    ) -> None:
        """Add a new reminder.

        Args:
            interaction (discord.Interaction): The interaction object for the command.
            message (str): The content of the reminder.
            time (str): The time of the reminder. (e.g. Friday at 3 PM)
            channel (discord.TextChannel, optional): The channel to send the reminder to. Defaults to current channel.
            user (discord.User, optional): Send reminder as a DM to this user. Defaults to None.
            dm_and_current_channel (bool, optional): Send reminder as a DM to the user and in this channel. Defaults to False.
        """
        await interaction.response.defer()

        logger.info(f"New reminder from {interaction.user} ({interaction.user.id}) in {interaction.channel}")
        logger.info(f"Arguments: {locals()}")

        # Check if we have access to the specified channel or the current channel
        target_channel: InteractionChannel | discord.TextChannel | None = channel or interaction.channel
        if target_channel and interaction.guild and not target_channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.followup.send(content=f"I don't have permission to send messages in <#{target_channel.id}>.", ephemeral=True)

        # Get the channel ID
        channel_id: int | None = channel.id if channel else (interaction.channel.id if interaction.channel else None)
        if not channel_id:
            await interaction.followup.send(content="Failed to get channel.", ephemeral=True)
            return

        # Ensure the guild is valid
        guild: discord.Guild | None = interaction.guild or None
        if not guild:
            await interaction.followup.send(content="Failed to get guild.", ephemeral=True)
            return

        dm_message: str = ""
        if user:
            parsed_time: datetime.datetime | None = parse_time(date_to_parse=time)
            if not parsed_time:
                await interaction.followup.send(content=f"Failed to parse time: {time}.", ephemeral=True)
                return

            user_reminder: Job = scheduler.add_job(
                func=send_to_user,
                trigger="date",
                run_date=parsed_time,
                kwargs={
                    "user_id": user.id,
                    "guild_id": guild.id,
                    "message": message,
                },
            )
            logger.info(f"User reminder job created: {user_reminder} for {user.id} at {parsed_time}")

            dm_message = f" and a DM to {user.display_name}"
            if not dm_and_current_channel:
                msg = (
                    f"Hello {interaction.user.display_name},\n"
                    f"I will send a DM to {user.display_name} at:\n"
                    f"First run in {calculate(user_reminder)} with the message:\n**{message}**."
                )
                await interaction.followup.send(content=msg)
                return

        # Create channel reminder job
        channel_job: Job = scheduler.add_job(
            func=send_to_discord,
            trigger="date",
            run_date=parse_time(date_to_parse=time),
            kwargs={
                "channel_id": channel_id,
                "message": message,
                "author_id": interaction.user.id,
            },
        )
        logger.info(f"Channel reminder job created: {channel_job} for {channel_id}")

        msg: str = (
            f"Hello {interaction.user.display_name},\n"
            f"I will notify you in <#{channel_id}>{dm_message}.\n"
            f"First run in {calculate(channel_job)} with the message:\n**{message}**."
        )

        await interaction.followup.send(content=msg)

    # /remind event
    @discord.app_commands.command(name="event", description="Add a new Discord event.")
    async def add_event(
        self,
        interaction: discord.Interaction,
        message: str,
        event_start: str,
        event_end: str,
        location: str,
        reason: str | None = None,
    ) -> None:
        """Add a new reminder.

        Args:
            interaction (discord.Interaction): The interaction object for the command.
            message (str): The description of the scheduled event.
            event_start (str): The scheduled start time of the scheduled event. Will get parsed.
            event_end (str, optional): The scheduled end time of the scheduled event. Will get parsed.
            reason (str, optional): The reason for creating this scheduled event. Shows up on the audit log.
            location (str, optional): The location of the scheduled event.
        """
        await interaction.response.defer()

        logger.info(f"New event from {interaction.user} ({interaction.user.id}) in {interaction.channel}")
        logger.info(f"Arguments: {locals()}")

        # Check if we have a valid guild
        guild: discord.Guild | None = interaction.guild
        if not guild:
            await interaction.followup.send(content="This command can only be used in a server.", ephemeral=True)
            return

        # Check if we have permission to create events
        if not guild.me.guild_permissions.create_events:
            await interaction.followup.send(content="I don't have permission to create events in this guild.", ephemeral=True)
            return

        event_start_time: datetime.datetime | None = parse_time(date_to_parse=event_start)
        event_end_time: datetime.datetime | None = parse_time(date_to_parse=event_end)

        if not event_start_time or not event_end_time:
            await interaction.followup.send(content=f"Failed to parse time: {event_start} or {event_end}.", ephemeral=True)
            return

        # If event_start_time is in the past, make it now + 5 seconds
        start_immediately: bool = False
        if event_start_time < datetime.datetime.now(event_start_time.tzinfo):
            start_immediately = True
            event_start_time = datetime.datetime.now(event_start_time.tzinfo) + datetime.timedelta(seconds=5)
            await interaction.followup.send(content="Event start time was in the past. Starting event in 5 seconds instead.")

        reason_msg: str = f"Event created by {interaction.user} ({interaction.user.id})."

        event: discord.ScheduledEvent = await guild.create_scheduled_event(
            name=message,
            start_time=event_start_time,
            entity_type=discord.EntityType.external,
            privacy_level=discord.PrivacyLevel.guild_only,
            end_time=event_end_time,
            reason=reason or reason_msg,
            location=location,
        )

        if start_immediately:
            await event.start()

        msg: str = f"Event '{event.name}' created successfully!\n"

        if event.start_time:
            msg += f"Start Time: <t:{int(event.start_time.timestamp())}:R>\n"

        if event.end_time:
            msg += f"End Time: <t:{int(event.end_time.timestamp())}:R>\n"

        if event.channel_id:
            msg += f"Channel: <#{event.channel_id}>\n"

        if event.location:
            msg += f"Location: {event.location}\n"

        if event.creator_id:
            msg += f"Created by: <@{event.creator_id}>"

        await interaction.followup.send(content=msg)

    # /remind list
    @discord.app_commands.command(name="list", description="List, pause, unpause, and remove reminders.")
    async def list(self, interaction: discord.Interaction) -> None:
        """List all reminders with pagination and buttons for deleting and modifying jobs.

        Args:
            interaction(discord.Interaction): The interaction object for the command.
        """
        await interaction.response.defer()

        user: discord.User | discord.Member = interaction.user
        if not isinstance(user, discord.Member):
            await interaction.followup.send(content="This command can only be used in a server.", ephemeral=True)
            return

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send(content="This command can only be used in a text channel.", ephemeral=True)
            return

        logger.info(f"Listing reminders for {user} ({user.id}) in {interaction.channel}")
        logger.info(f"Arguments: {locals()}")

        jobs: list[Job] = scheduler.get_jobs()
        if not jobs:
            await interaction.followup.send(content="No scheduled jobs found in the database.", ephemeral=True)
            return

        guild: discord.Guild | None = interaction.guild
        if not guild:
            await interaction.followup.send(content="Failed to get guild.", ephemeral=True)
            return

        message: discord.InteractionMessage = await interaction.original_response()

        job_summary: list[str] = generate_reminder_summary(ctx=interaction)

        for i, msg in enumerate(job_summary):
            if i == 0:
                await message.edit(content=msg)
            else:
                await interaction.followup.send(content=msg)

    # /remind cron
    @discord.app_commands.command(name="cron", description="Create new cron job. Works like UNIX cron.")
    async def cron(
        self,
        interaction: discord.Interaction,
        message: str,
        year: str | None = None,
        month: str | None = None,
        day: str | None = None,
        week: str | None = None,
        day_of_week: str | None = None,
        hour: str | None = None,
        minute: str | None = None,
        second: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        timezone: str | None = None,
        jitter: int | None = None,
        channel: discord.TextChannel | None = None,
        user: discord.User | None = None,
        dm_and_current_channel: bool | None = None,
    ) -> None:
        """Create a new cron job.

        Args that are None will be defaulted to *.

        Args:
            interaction (discord.Interaction): The interaction object for the command.
            message (str): The content of the reminder.
            year (str): 4-digit year. Defaults to *.
            month (str): Month (1-12). Defaults to *.
            day (str): Day of the month (1-31). Defaults to *.
            week (str): ISO Week of the year (1-53). Defaults to *.
            day_of_week (str): Number or name of weekday (0-6 or mon,tue,wed,thu,fri,sat,sun).
            hour (str): Hour (0-23). Defaults to *.
            minute (str): Minute (0-59). Defaults to *.
            second (str): Second (0-59). Defaults to *.
            start_date (str): Earliest possible date/time to trigger on (inclusive). Will get parsed.
            end_date (str): Latest possible date/time to trigger on (inclusive). Will get parsed.
            timezone (str): Time zone to use for the date/time calculations Defaults to scheduler timezone.
            jitter (int, optional): Delay the job execution by jitter seconds at most.
            channel (discord.TextChannel, optional): The channel to send the reminder to. Defaults to current channel.
            user (discord.User, optional): Send reminder as a DM to this user. Defaults to None.
            dm_and_current_channel (bool, optional): If user is provided, send reminder as a DM to the user and in this channel. Defaults to only the user.
        """
        await interaction.response.defer()

        # Log kwargs
        logger.info(f"New cron job from {interaction.user} ({interaction.user.id}) in {interaction.channel}")
        logger.info(f"Cron job arguments: {locals()}")

        # Get the channel ID
        channel_id: int | None = channel.id if channel else (interaction.channel.id if interaction.channel else None)
        if not channel_id:
            await interaction.followup.send(content="Failed to get channel.", ephemeral=True)
            return

        # Ensure the guild is valid
        guild: discord.Guild | None = interaction.guild or None
        if not guild:
            await interaction.followup.send(content="Failed to get guild.", ephemeral=True)
            return

        # Create user DM reminder job if user is specified
        dm_message: str = ""
        if user:
            user_reminder: Job = scheduler.add_job(
                func=send_to_user,
                trigger="cron",
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
                    "user_id": user.id,
                    "guild_id": guild.id,
                    "message": message,
                },
            )

            dm_message = f" and a DM to {user.display_name}"
            if not dm_and_current_channel:
                await interaction.followup.send(
                    content=f"Hello {interaction.user.display_name},\n"
                    f"I will send a DM to {user.display_name} at:\n"
                    f"First run in {calculate(user_reminder)} with the message:\n**{message}**.",
                )
                return

        # Create channel reminder job
        channel_job: Job = scheduler.add_job(
            func=send_to_discord,
            trigger="cron",
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
                "channel_id": channel_id,
                "message": message,
                "author_id": interaction.user.id,
            },
        )

        await interaction.followup.send(
            content=f"Hello {interaction.user.display_name},\n"
            f"I will notify you in <#{channel_id}>{dm_message}.\n"
            f"First run in {calculate(channel_job)} with the message:\n**{message}**.",
        )

    # /remind interval
    @discord.app_commands.command(
        name="interval",
        description="Create a new reminder that triggers based on an interval.",
    )
    async def interval(
        self,
        interaction: discord.Interaction,
        message: str,
        weeks: int = 0,
        days: int = 0,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
        start_date: str | None = None,
        end_date: str | None = None,
        timezone: str | None = None,
        jitter: int | None = None,
        channel: discord.TextChannel | None = None,
        user: discord.User | None = None,
        dm_and_current_channel: bool | None = None,
    ) -> None:
        """Create a new reminder that triggers based on an interval.

        Args:
            interaction (discord.Interaction): The interaction object for the command.
            message (str): The content of the reminder.
            weeks (int, optional): Number of weeks between each run. Defaults to 0.
            days (int, optional): Number of days between each run. Defaults to 0.
            hours (int, optional): Number of hours between each run. Defaults to 0.
            minutes (int, optional): Number of minutes between each run. Defaults to 0.
            seconds (int, optional): Number of seconds between each run. Defaults to 0.
            start_date (str, optional): Earliest possible date/time to trigger on (inclusive). Will get parsed.
            end_date (str, optional): Latest possible date/time to trigger on (inclusive). Will get parsed.
            timezone (str, optional): Time zone to use for the date/time calculations Defaults to scheduler timezone.
            jitter (int, optional): Delay the job execution by jitter seconds at most.
            channel (discord.TextChannel, optional): The channel to send the reminder to. Defaults to current channel.
            user (discord.User, optional): Send reminder as a DM to this user. Defaults to None.
            dm_and_current_channel (bool, optional): If user is provided, send reminder as a DM to the user and in this channel. Defaults to only the user.
        """
        await interaction.response.defer()

        logger.info(f"New interval job from {interaction.user} ({interaction.user.id}) in {interaction.channel}")
        logger.info(f"Arguments: {locals()}")

        # Only allow intervals of 30 seconds or more so we don't spam the channel
        if weeks == days == hours == minutes == 0 and seconds < 30:
            await interaction.followup.send(content="Interval must be at least 30 seconds.", ephemeral=True)
            return

        # Check if we have access to the specified channel or the current channel
        target_channel: InteractionChannel | None = channel or interaction.channel
        if target_channel and interaction.guild and not target_channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.followup.send(
                content=f"I don't have permission to send messages in <#{target_channel.id}>.",
                ephemeral=True,
            )

        # Get the channel ID
        channel_id: int | None = channel.id if channel else (interaction.channel.id if interaction.channel else None)
        if not channel_id:
            await interaction.followup.send(content="Failed to get channel.", ephemeral=True)
            return

        # Ensure the guild is valid
        guild: discord.Guild | None = interaction.guild or None
        if not guild:
            await interaction.followup.send(content="Failed to get guild.", ephemeral=True)
            return

        # Create user DM reminder job if user is specified
        dm_message: str = ""
        if user:
            dm_job: Job = scheduler.add_job(
                func=send_to_user,
                trigger="interval",
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
                    "user_id": user.id,
                    "guild_id": guild.id,
                    "message": message,
                },
            )

            dm_message = f" and a DM to {user.display_name} "
            if not dm_and_current_channel:
                await interaction.followup.send(
                    content=f"Hello {interaction.user.display_name},\n"
                    f"I will send a DM to {user.display_name} at:\n"
                    f"First run in {calculate(dm_job)} with the message:\n**{message}**.",
                )

        # Create channel reminder job
        channel_job: Job = scheduler.add_job(
            func=send_to_discord,
            trigger="interval",
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
                "channel_id": channel_id,
                "message": message,
                "author_id": interaction.user.id,
            },
        )

        await interaction.followup.send(
            content=f"Hello {interaction.user.display_name},\n"
            f"I will notify you in <#{channel_id}>{dm_message}.\n"
            f"First run in {calculate(channel_job)} with the message:\n**{message}**.",
        )

    # /remind backup
    @discord.app_commands.command(name="backup", description="Backup all reminders to a file.")
    async def backup(self, interaction: discord.Interaction, all_servers: bool = False) -> None:
        """Backup all reminders to a file.

        Args:
            interaction (discord.Interaction): The interaction object for the command.
            all_servers (bool): Backup all servers or just the current server. Defaults to only the current server.
        """
        await interaction.response.defer()

        logger.info(f"Backing up reminders for {interaction.user} ({interaction.user.id}) in {interaction.channel}")
        logger.info(f"Arguments: {locals()}")

        # Retrieve all jobs
        with tempfile.NamedTemporaryFile(mode="r+", delete=False, encoding="utf-8", suffix=".json") as temp_file:
            # Export jobs to a temporary file
            scheduler.export_jobs(temp_file.name)

            # Load the exported jobs
            temp_file.seek(0)
            jobs_data = json.load(temp_file)

        # Amount of jobs before filtering
        amount_of_jobs: int = len(jobs_data.get("jobs", []))

        if not all_servers:
            interaction_channel: InteractionChannel | None = interaction.channel
            if not interaction_channel:
                await interaction.followup.send(content="Failed to get channel.", ephemeral=True)
                return

            if not isinstance(interaction.user, discord.Member):
                await interaction.followup.send(content="Failed to get user.", ephemeral=True)
                return

            is_admin: bool = interaction_channel.permissions_for(interaction.user).administrator
            if not is_admin:
                await interaction.followup.send(content="You must be an administrator to backup all servers.", ephemeral=True)
                return

            # Can't be 0 because that's the default value for jobs without a guild
            guild_id: int = interaction.guild.id if interaction.guild else -1
            channels_in_this_guild: list[int] = [c.id for c in interaction.guild.channels] if interaction.guild else []
            logger.debug(f"Guild ID: {guild_id}")

            for job in jobs_data.get("jobs", []):
                # Check if the job is in the current guild
                job_guild_id = int(job.get("kwargs", {}).get("guild_id", 0))
                if job_guild_id and job_guild_id != guild_id:
                    logger.debug(f"Skipping job: {job.get('id')} because it's not in the current guild.")
                    jobs_data["jobs"].remove(job)

                # Check if the channel is in the current guild
                if job.get("kwargs", {}).get("channel_id") not in channels_in_this_guild:
                    logger.debug(f"Skipping job: {job.get('id')} because it's not in the current guild.")
                    jobs_data["jobs"].remove(job)

        msg: str = "All reminders in this server have been backed up." if not all_servers else "All reminders have been backed up."
        msg += "\nYou can restore them using `/remind restore`."

        if not all_servers:
            msg += f"\nAmount of jobs on all servers: {amount_of_jobs}, in this server: {len(jobs_data.get('jobs', []))}"
            msg += "\nYou can use `/remind backup all_servers:True` to backup all servers."
        else:
            msg += f"\nAmount of jobs: {amount_of_jobs}"

        # Write the data to a new file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8", suffix=".json") as output_file:
            file_name: str = f"reminders-backup-{datetime.datetime.now(tz=scheduler.timezone)}.json"
            json.dump(jobs_data, output_file, indent=4)
            output_file.seek(0)

            await interaction.followup.send(content=msg, file=discord.File(output_file.name, filename=file_name))

    # /remind restore
    @discord.app_commands.command(name="restore", description="Restore reminders from a file.")
    async def restore(self, interaction: discord.Interaction) -> None:
        """Restore reminders from a file.

        Args:
            interaction (discord.Interaction): The interaction object for the command.
        """
        await interaction.response.defer()

        logger.info(f"Restoring reminders from file for {interaction.user} ({interaction.user.id}) in {interaction.channel}")
        logger.info(f"Arguments: {locals()}")

        # Tell to reply with the file to this message
        await interaction.followup.send(content="Please reply to this message with the backup file.")

        # Get the old jobs
        old_jobs: list[Job] = scheduler.get_jobs()

        # Wait for the reply
        while True:
            try:
                reply: discord.Message | None = await bot.wait_for("message", timeout=60, check=lambda m: m.author == interaction.user)
            except TimeoutError:
                edit_msg = "~~Please reply to this message with the backup file.~~\nTimed out after 60 seconds."
                await interaction.edit_original_response(content=edit_msg)
                return

            if not reply.channel:
                await interaction.followup.send(content="No channel found. Please try again.")
                continue

            # Fetch the message by its ID to ensure we have the latest data
            reply = await reply.channel.fetch_message(reply.id)

            if not reply or not reply.attachments:
                await interaction.followup.send(content="No file attached. Please try again.")
                continue
            break

        # Get the attachment
        attachment: discord.Attachment = reply.attachments[0]
        if not attachment or not attachment.filename.endswith(".json"):
            await interaction.followup.send(
                content=f"Invalid file type. Should be a JSON file not '{attachment.filename}'. Please try again.",
            )
            return

        jobs_already_exist: list[str] = []

        # Save the file to a temporary file and import the jobs
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8", suffix=".json") as temp_file:
            logger.info(f"Saving attachment to {temp_file.name}")
            await attachment.save(Path(temp_file.name))

            # Load the jobs data from the file
            temp_file.seek(0)
            jobs_data: dict = json.load(temp_file)

            logger.info("Importing jobs from file")
            logger.debug(f"Jobs data: {jobs_data}")

            with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8", suffix=".json") as temp_import_file:
                # We can't import jobs with the same ID so remove them from the JSON
                jobs = [job for job in jobs_data.get("jobs", []) if not scheduler.get_job(job.get("id"))]
                jobs_already_exist = [job.get("id") for job in jobs_data.get("jobs", []) if scheduler.get_job(job.get("id"))]
                jobs_data["jobs"] = jobs
                for job_id in jobs_already_exist:
                    logger.debug(f"Skipping importing '{job_id}' because it already exists in the db.")

                logger.debug(f"Jobs data after filtering: {jobs_data}")
                logger.info(f"Jobs already exist: {jobs_already_exist}")

                # Write the new data to a temporary file
                json.dump(jobs_data, temp_import_file)
                temp_import_file.seek(0)

                # Import the jobs
                scheduler.import_jobs(temp_import_file.name)

        # Get the new jobs
        new_jobs: list[Job] = scheduler.get_jobs()

        # Get the difference
        added_jobs: list[Job] = [job for job in new_jobs if job not in old_jobs]

        if added_jobs:
            msg: str = "Reminders restored successfully.\nAdded jobs:\n"
            for j in added_jobs:
                msg += f"* Message: **{j.kwargs.get('message', 'No message found')}** {calculate(j) or 'N/A'}\n"

            await interaction.followup.send(content=msg)
        else:
            await interaction.followup.send(content="No new reminders were added.")

    # /remind remove
    @discord.app_commands.command(name="remove", description="Remove a reminder")
    async def remove(self, interaction: discord.Interaction, job_id: str) -> None:
        """Remove a scheduled reminder.

        Args:
            interaction (discord.Interaction): The interaction object for the command.
            job_id (str): The identifier of the job to remove.
        """
        await interaction.response.defer()

        logger.debug(f"Removing reminder with ID {job_id} for {interaction.user} ({interaction.user.id}) in {interaction.channel}")
        logger.debug(f"Arguments: {locals()}")

        try:
            job: Job | None = scheduler.get_job(job_id)
            if not job:
                await interaction.followup.send(content=f"Reminder with ID {job_id} not found.", ephemeral=True)
                return
            scheduler.remove_job(job_id)
            logger.info(f"Removed job {job_id}. {job.__getstate__()}")
            await interaction.followup.send(
                content=f"Reminder with ID {job_id} removed successfully.\n{generate_markdown_state(job.__getstate__())}",
            )
        except JobLookupError as e:
            logger.exception(f"Failed to remove job {job_id}")
            await interaction.followup.send(content=f"Failed to remove reminder with ID {job_id}. {e}", ephemeral=True)

        logger.info(f"Job {job_id} removed from the scheduler.")


intents: discord.Intents = discord.Intents.default()
intents.guild_scheduled_events = True

bot = RemindBotClient(intents=intents)

# Add the group to the bot
remind_group = RemindGroup()
bot.tree.add_command(remind_group)


def send_webhook(custom_url: str = "", message: str = "") -> None:
    """Send a webhook to Discord.

    Args:
        custom_url: The custom webhook URL to send the message to. If not provided, uses the WEBHOOK_URL environment variable.
        message: The message that will be sent to Discord.
    """
    logger.info(f"Sending webhook to '{custom_url}' with message: '{message}'")

    if not message:
        logger.error("No message provided.")
        message = "No message provided."

    webhook_url: str = os.getenv("WEBHOOK_URL", default="")
    url: str = custom_url or webhook_url
    if not url:
        logger.error("No webhook URL provided.")
        return

    webhook: DiscordWebhook = DiscordWebhook(url=url, content=message, rate_limit_retry=True)
    webhook_response: Response = webhook.execute()

    logger.info(f"Webhook response: {webhook_response}")


async def send_to_discord(channel_id: int, message: str, author_id: int) -> None:
    """Send a message to Discord.

    Args:
        channel_id: The Discord channel ID.
        message: The message.
        author_id: User we should ping.
    """
    logger.info(f"Sending message to channel '{channel_id}' with message: '{message}'")

    channel: GuildChannel | discord.Thread | PrivateChannel | None = bot.get_channel(channel_id)
    if channel is None:
        channel = await bot.fetch_channel(channel_id)

    # Channels we can't send messages to
    if isinstance(channel, discord.ForumChannel | discord.CategoryChannel | PrivateChannel):
        logger.warning(f"We haven't implemented sending messages to this channel type {type(channel)}")
        return

    await channel.send(f"<@{author_id}>\n{message}")


async def send_to_user(user_id: int, guild_id: int, message: str) -> None:
    """Send a message to a user via DM.

    Args:
        user_id: The user ID to send the message to.
        guild_id: The guild ID to get the user from.
        message: The message to send.
    """
    logger.info(f"Sending message to user {user_id} in guild {guild_id}")
    try:
        guild: discord.Guild | None = bot.get_guild(guild_id)
        if guild is None:
            guild = await bot.fetch_guild(guild_id)
    except discord.NotFound:
        logger.exception(f"Guild not found. Current guilds: {bot.guilds}")
        return
    except discord.HTTPException:
        logger.exception(f"Failed to fetch guild {guild_id}")
        return

    try:
        member: discord.Member | None = guild.get_member(user_id)
        if member is None:
            member = await guild.fetch_member(user_id)
    except discord.Forbidden:
        logger.exception(f"We do not have access to the guild. Guild: {guild_id}, User: {user_id}")
        return
    except discord.NotFound:
        logger.exception(f"Member not found. Guild: {guild_id}, User: {user_id}")
        return
    except discord.HTTPException:
        logger.exception(f"Fetching the member failed. Guild: {guild_id}, User: {user_id}")
        return

    try:
        await member.send(message)
    except discord.HTTPException:
        logger.exception(f"Failed to send message '{message}' to user '{user_id}' in guild '{guild_id}'")


if __name__ == "__main__":
    bot_token: str = os.getenv("BOT_TOKEN", default="")
    if not bot_token:
        msg = "Missing bot token. Please set the BOT_TOKEN environment variable. Read the README for more information."
        raise ValueError(msg)

    logger.info("Starting bot.")
    bot.run(bot_token)
