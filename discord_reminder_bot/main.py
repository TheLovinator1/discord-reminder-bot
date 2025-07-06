from __future__ import annotations

import datetime
import json
import os
import sys
import tempfile
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

import apscheduler
import apscheduler.triggers
import apscheduler.triggers.cron
import apscheduler.triggers.date
import apscheduler.triggers.interval
import discord
import sentry_sdk
from apscheduler import events
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED, JobExecutionEvent
from apscheduler.jobstores.base import JobLookupError
from discord.abc import PrivateChannel
from discord.utils import escape_markdown
from discord_webhook import DiscordWebhook
from loguru import logger

from discord_reminder_bot.helpers import calculate, generate_markdown_state, generate_state, get_human_readable_time, parse_time
from discord_reminder_bot.modals import CronReminderModifyModal, DateReminderModifyModal, IntervalReminderModifyModal
from discord_reminder_bot.settings import scheduler

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import CoroutineType

    from apscheduler.job import Job
    from discord.guild import GuildChannel
    from discord.interactions import InteractionChannel
    from requests import Response


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
        super().__init__(intents=intents, max_messages=None)
        self.tree = discord.app_commands.CommandTree(self)

    async def on_error(self, event_method: str, *args: list[Any], **kwargs: dict[str, Any]) -> None:
        """Log errors that occur in the bot."""
        logger.exception(f"An error occurred in {event_method} with args: {args} and kwargs: {kwargs}")
        sentry_sdk.capture_exception()  # TODO(TheLovinator): Add more context to the error  # noqa: TD003

    async def on_ready(self) -> None:
        """Called when the client is done preparing the data received from Discord. Usually after login is successful and the Client.guilds and co. are filled up.

        Warning:
            This function is not guaranteed to be the first event called. Likewise, this function is not guaranteed to only be called once.
            discord.py implements reconnection logic and thus will end up calling this event whenever a RESUME request fails.
        """
        logger_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | {extra[session_id]} | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
        logger.configure(extra={"session_id": self.ws.session_id})

        logger.remove()
        logger.add(sys.stderr, format=logger_format)
        logger.info(f"Logged in as {self.user} ({self.user.id if self.user else 'Unknown'})")

    async def setup_hook(self) -> None:
        """Setup the bot."""
        scheduler.add_listener(my_listener, EVENT_JOB_MISSED | EVENT_JOB_ERROR)
        jobs: list[Job] = scheduler.get_jobs()
        if jobs:
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
        logger.info("Command tree synced.")

        if not scheduler.running:
            logger.info("Starting scheduler.")
            scheduler.start()
        else:
            logger.error("Scheduler is already running.")


def format_job_for_ui(job: Job) -> str:
    """Format a single job for display in the UI.

    Args:
        job (Job): The job to format.

    Returns:
        str: The formatted string.
    """
    msg: str = f"\nMessage: {job.kwargs.get('message', '')}\n"
    msg += f"ID: {job.id}\n"
    msg += f"Trigger: {job.trigger} {get_human_readable_time(job)}\n"

    if job.kwargs.get("user_id"):
        msg += f"User: <@{job.kwargs.get('user_id')}>\n"
    if job.kwargs.get("guild_id"):
        guild_id: int = job.kwargs.get("guild_id")
        msg += f"Guild: {guild_id}\n"
    if job.kwargs.get("author_id"):
        author_id: int = job.kwargs.get("author_id")
        msg += f"Author: <@{author_id}>\n"
    if job.kwargs.get("channel_id"):
        channel = bot.get_channel(job.kwargs.get("channel_id"))
        if channel and isinstance(channel, discord.abc.GuildChannel | discord.Thread):
            msg += f"Channel: #{channel.name}\n"

    msg += f"\nData:\n{generate_state(job.__getstate__(), job)}\n"

    logger.debug(f"Formatted job for UI: {msg}")
    return msg


class ReminderListView(discord.ui.View):
    """A view for listing reminders with pagination and action buttons."""

    def __init__(self, jobs: list[Job], interaction: discord.Interaction, jobs_per_page: int = 1) -> None:
        """Initialize the view with a list of jobs and interaction.

        Args:
            jobs (list[Job]): The list of jobs to display.
            interaction (discord.Interaction): The interaction that triggered this view.
            jobs_per_page (int): The number of jobs to display per page. Defaults to 1.
        """
        super().__init__(timeout=180)
        self.jobs: list[Job] = jobs
        self.interaction: discord.Interaction[discord.Client] = interaction
        self.jobs_per_page: int = jobs_per_page
        self.current_page = 0
        self.message: discord.InteractionMessage | None = None

        self.update_view()

    @property
    def total_pages(self) -> int:
        """Calculate the total number of pages based on the number of jobs and jobs per page."""
        return max(1, (len(self.jobs) + self.jobs_per_page - 1) // self.jobs_per_page)

    def update_view(self) -> None:
        """Update the buttons and job actions for the current page."""
        self.clear_items()

        # Ensure current_page is in valid bounds
        self.current_page: int = max(0, min(self.current_page, self.total_pages - 1))

        # Pagination buttons
        buttons: list[tuple[str, Callable[..., CoroutineType[Any, Any, None]], bool] | tuple[str, None, bool]] = [
            ("⏮️", self.goto_first_page, self.current_page == 0),
            ("◀️", self.goto_prev_page, self.current_page == 0),
            (f"{self.current_page + 1}/{self.total_pages}", None, True),
            ("▶️", self.goto_next_page, self.current_page >= self.total_pages - 1),
            ("⏭️", self.goto_last_page, self.current_page >= self.total_pages - 1),
        ]
        for label, callback, disabled in buttons:
            btn = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary, disabled=disabled)
            if callback:
                btn.callback = callback
            self.add_item(btn)

        # Job action buttons
        start: int = self.current_page * self.jobs_per_page
        end: int = min(start + self.jobs_per_page, len(self.jobs))
        for i, job in enumerate(self.jobs[start:end]):
            row: int = i + 1  # pagination is row 0
            job_id = job.id
            label: str = "▶️ Unpause" if job.next_run_time is None else "⏸️ Pause"

            delete = discord.ui.Button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=row)
            delete.callback = partial(self.handle_delete, job_id=job_id)

            modify = discord.ui.Button(label="✏️ Modify", style=discord.ButtonStyle.secondary, row=row)
            modify.callback = partial(self.handle_modify, job_id=job_id)

            pause = discord.ui.Button(label=label, style=discord.ButtonStyle.success, row=row)
            pause.callback = partial(self.handle_pause_unpause, job_id=job_id)

            self.add_item(delete)
            self.add_item(modify)
            self.add_item(pause)

    def get_page_content(self) -> str:
        """Get the content for the current page of reminders.

        Returns:
            str: The formatted string for the current page.
        """
        start: int = self.current_page * self.jobs_per_page
        end: int = min(start + self.jobs_per_page, len(self.jobs))
        jobs: list[Job] = self.jobs[start:end]

        if not jobs:
            return "No reminders found on this page."

        job: Job = jobs[0]
        return f"```{format_job_for_ui(job)}```"

    async def refresh(self, interaction: discord.Interaction) -> None:
        """Refresh the view and update the message with the current page content.

        Args:
            interaction (discord.Interaction): The interaction that triggered this refresh.
        """
        self.update_view()
        if self.message:
            await self.message.edit(content=self.get_page_content(), view=self)
        else:
            await interaction.response.edit_message(content=self.get_page_content(), view=self)

    async def goto_first_page(self, interaction: discord.Interaction) -> None:
        """Go to the first page of reminders."""
        await interaction.response.defer()
        self.current_page = 0
        await self.refresh(interaction)

    async def goto_prev_page(self, interaction: discord.Interaction) -> None:
        """Go to the previous page of reminders."""
        await interaction.response.defer()
        self.current_page -= 1
        await self.refresh(interaction)

    async def goto_next_page(self, interaction: discord.Interaction) -> None:
        """Go to the next page of reminders."""
        await interaction.response.defer()
        self.current_page += 1
        await self.refresh(interaction)

    async def goto_last_page(self, interaction: discord.Interaction) -> None:
        """Go to the last page of reminders."""
        await interaction.response.defer()
        self.current_page = self.total_pages - 1
        await self.refresh(interaction)

    async def handle_delete(self, interaction: discord.Interaction, job_id: str) -> None:
        """Handle the deletion of a reminder job.

        Args:
            interaction (discord.Interaction): The interaction that triggered this deletion.
            job_id (str): The ID of the job to delete.
        """
        await interaction.response.defer(ephemeral=True)
        try:
            scheduler.remove_job(job_id)
            self.jobs = [job for job in self.jobs if job.id != job_id]
            await interaction.followup.send(f"Reminder `{escape_markdown(job_id)}` deleted.", ephemeral=True)
            if (
                not self.jobs[self.current_page * self.jobs_per_page : (self.current_page + 1) * self.jobs_per_page]
                and self.current_page > 0
            ):
                self.current_page -= 1
        except JobLookupError:
            await interaction.followup.send(f"Job `{escape_markdown(job_id)}` not found.", ephemeral=True)
        except Exception as e:  # noqa: BLE001
            logger.exception(f"Failed to delete job {job_id}: {e}")
            await interaction.followup.send(f"Failed to delete job `{escape_markdown(job_id)}`.", ephemeral=True)
        await self.refresh(interaction)

    async def handle_modify(self, interaction: discord.Interaction, job_id: str) -> None:
        """Handle the modification of a reminder job.

        Args:
            interaction (discord.Interaction): The interaction that triggered this modification.
            job_id (str): The ID of the job to modify.
        """
        job: Job | None = scheduler.get_job(job_id)
        if not job:
            await interaction.response.send_message(f"Failed to get job for '{job_id}'", ephemeral=True)
            return

        # Check if the job is a date-based job
        if isinstance(job.trigger, apscheduler.triggers.date.DateTrigger):
            await interaction.response.send_modal(DateReminderModifyModal(job))
            return
        if isinstance(job.trigger, apscheduler.triggers.cron.CronTrigger):
            await interaction.response.send_modal(CronReminderModifyModal(job))
            return
        if isinstance(job.trigger, apscheduler.triggers.interval.IntervalTrigger):
            await interaction.response.send_modal(IntervalReminderModifyModal(job))
            return

        logger.error(f"Job {job_id} is not a date-based job, cron job, or interval job. Cannot modify.")
        await interaction.response.send_message(
            f"Job is not a date-based job, cron job, or interval job. Cannot modify.\n"
            f"Job ID: `{escape_markdown(job_id)}`\n"
            f"Job Trigger: `{job.trigger}`",
            ephemeral=True,
        )

    async def handle_pause_unpause(self, interaction: discord.Interaction, job_id: str) -> None:
        """Handle pausing or unpausing a reminder job.

        Args:
            interaction (discord.Interaction): The interaction that triggered this action.
            job_id (str): The ID of the job to pause or unpause.
        """
        await interaction.response.defer(ephemeral=True)
        try:
            job: Job | None = scheduler.get_job(job_id)
            if not job:
                await interaction.followup.send(f"Job `{escape_markdown(job_id)}` not found.", ephemeral=True)
                return

            if job.next_run_time is None:
                scheduler.resume_job(job_id)
                msg = f"Reminder `{escape_markdown(job_id)}` unpaused."
            else:
                scheduler.pause_job(job_id)
                msg = f"Reminder `{escape_markdown(job_id)}` paused."

            # Update only the affected job in self.jobs
            updated_job = scheduler.get_job(job_id)
            if updated_job:
                for i, j in enumerate(self.jobs):
                    if j.id == job_id:
                        self.jobs[i] = updated_job
                        break

            await interaction.followup.send(msg, ephemeral=True)
        except JobLookupError:
            await interaction.followup.send(f"Job `{escape_markdown(job_id)}` not found.", ephemeral=True)
        except Exception as e:  # noqa: BLE001
            logger.exception(f"Failed to pause/unpause job {job_id}: {e}")
            await interaction.followup.send(f"Failed to pause/unpause job `{escape_markdown(job_id)}`.", ephemeral=True)
        await self.refresh(interaction)

    async def on_timeout(self) -> None:
        """Handle the timeout of the view."""
        logger.info("ReminderListView timed out, disabling buttons.")
        if self.message:
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if the interaction is valid for this view.

        Args:
            interaction (discord.Interaction): The interaction to check.

        Returns:
            bool: True if the interaction is valid, False otherwise.
        """
        if interaction.user != self.interaction.user:
            logger.debug(f"Interaction user {interaction.user} is not the same as the view's interaction user {self.interaction.user}.")
            await interaction.response.send_message("This is not your reminder list!", ephemeral=True)
            return False
        return True


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

        all_jobs: list[Job] = scheduler.get_jobs()
        guild: discord.Guild | None = interaction.guild
        if not guild:
            await interaction.followup.send(content="Failed to get guild.", ephemeral=True)
            return

        # Filter jobs by guild
        guild_jobs: list[Job] = []
        channels_in_this_guild: list[int] = [c.id for c in guild.channels] if guild else []
        for job in all_jobs:
            guild_id_from_kwargs = int(job.kwargs.get("guild_id", 0))
            if guild_id_from_kwargs and guild_id_from_kwargs != guild.id:
                continue

            if job.kwargs.get("channel_id") not in channels_in_this_guild:
                continue

            guild_jobs.append(job)

        if not guild_jobs:
            await interaction.followup.send(content="No scheduled jobs found in this server.", ephemeral=True)
            return

        view = ReminderListView(jobs=guild_jobs, interaction=interaction)
        content = view.get_page_content()
        message = await interaction.followup.send(content=content, view=view)
        view.message = message  # Store the message for later edits

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

            dm_message = f" and a DM to {user.display_name}"
            if not dm_and_current_channel:
                await interaction.followup.send(
                    content=f"Hello {interaction.user.display_name},\n"
                    f"I will send a DM to {user.display_name} at:\n"
                    f"First run in {calculate(dm_job)} with the message:\n**{message}**.",
                )
                return

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
            # TODO(TheLovinator): This will probably fuck me in the ass in the future, so should probably not be -1 or 0.  # noqa: TD003
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

        # If we have no jobs left, return an error message
        if not jobs_data.get("jobs"):
            msg: str = "No reminders found in this server." if not all_servers else "No reminders found."
            await interaction.followup.send(content=msg, ephemeral=True)
            return

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
                content=f"Reminder with ID {job_id} removed successfully.\n{generate_markdown_state(job.__getstate__(), job=job)}",
            )
        except JobLookupError as e:
            logger.exception(f"Failed to remove job {job_id}")
            await interaction.followup.send(content=f"Failed to remove reminder with ID {job_id}. {e}", ephemeral=True)

        logger.info(f"Job {job_id} removed from the scheduler.")

    # /remind pause
    @discord.app_commands.command(name="pause", description="Pause a reminder")
    async def pause(self, interaction: discord.Interaction, job_id: str) -> None:
        """Pause a scheduled reminder.

        Args:
            interaction (discord.Interaction): The interaction object for the command.
            job_id (str): The identifier of the job to pause.
        """
        await interaction.response.defer()

        logger.debug(f"Pausing reminder with ID {job_id} for {interaction.user} ({interaction.user.id}) in {interaction.channel}")
        logger.debug(f"Arguments: {locals()}")

        try:
            job: Job | None = scheduler.get_job(job_id)
            if not job:
                await interaction.followup.send(content=f"Reminder with ID {job_id} not found.", ephemeral=True)
                return
            scheduler.pause_job(job_id)
            logger.info(f"Paused job {job_id}.")
            await interaction.followup.send(content=f"Reminder with ID {job_id} paused successfully.")
        except JobLookupError as e:
            logger.exception(f"Failed to pause job {job_id}")
            await interaction.followup.send(content=f"Failed to pause reminder with ID {job_id}. {e}", ephemeral=True)

        logger.info(f"Job {job_id} paused in the scheduler.")

    # /remind unpause
    @discord.app_commands.command(name="unpause", description="Unpause a reminder")
    async def unpause(self, interaction: discord.Interaction, job_id: str) -> None:
        """Unpause a scheduled reminder.

        Args:
            interaction (discord.Interaction): The interaction object for the command.
            job_id (str): The identifier of the job to unpause.
        """
        await interaction.response.defer()

        logger.debug(f"Unpausing reminder with ID {job_id} for {interaction.user} ({interaction.user.id}) in {interaction.channel}")
        logger.debug(f"Arguments: {locals()}")

        try:
            job: Job | None = scheduler.get_job(job_id)
            if not job:
                await interaction.followup.send(content=f"Reminder with ID {job_id} not found.", ephemeral=True)
                return
            scheduler.resume_job(job_id)
            logger.info(f"Unpaused job {job_id}.")
            await interaction.followup.send(content=f"Reminder with ID {job_id} unpaused successfully.")
        except JobLookupError as e:
            logger.exception(f"Failed to unpause job {job_id}")
            await interaction.followup.send(content=f"Failed to unpause reminder with ID {job_id}. {e}", ephemeral=True)

        logger.info(f"Job {job_id} unpaused in the scheduler.")


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
        author_id: User we should mention in the message.
    """
    logger.info(f"Sending message to channel '<#{channel_id}>' with message: '{message}'")

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
