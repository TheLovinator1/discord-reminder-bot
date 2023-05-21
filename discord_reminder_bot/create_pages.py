from collections.abc import Generator
from typing import TYPE_CHECKING, Literal

import interactions
from apscheduler.job import Job
from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.date import DateTrigger
from interactions import (
    ActionRow,
    Button,
    ButtonStyle,
    Channel,
    CommandContext,
    ComponentContext,
    Embed,
    Message,
    Modal,
    TextInput,
)
from interactions.ext.paginator import Page, Paginator, RowPosition

from discord_reminder_bot.countdown import calculate
from discord_reminder_bot.settings import scheduler

if TYPE_CHECKING:
    from datetime import datetime


max_message_length: Literal[1010] = 1010
max_title_length: Literal[90] = 90


def _get_trigger_text(job: Job) -> str:
    """Get trigger time from a reminder and calculate how many days, hours and minutes till trigger.

    Args:
        job: The job. Can be cron, interval or normal.

    Returns:
        str: The trigger time and countdown till trigger. If the job is paused, it will return "_Paused_".
    """
    # TODO: Add support for cron jobs and interval jobs
    trigger_time: datetime | None = job.trigger.run_date if type(job.trigger) is DateTrigger else job.next_run_time
    return "_Paused_" if trigger_time is None else f'{trigger_time.strftime("%Y-%m-%d %H:%M")} (in {calculate(job)})'


def _make_button(label: str, style: ButtonStyle) -> Button:
    """Make a button.

    Args:
        label: The label of the button.
        style: The style of the button.

    Returns:
        Button: The button.
    """
    return interactions.Button(
        label=label,
        style=style,
        custom_id=label.lower(),
    )


def _get_pause_or_unpause_button(job: Job) -> Button | None:
    """Get pause or unpause button.

    If the job is paused, it will return the unpause button.
    If the job is not paused, it will return the pause button.
    If the job is not a cron or interval job, it will return None.

    Args:
        job: The job. Can be cron, interval or normal.

    Returns:
        Button | None: The pause or unpause button. If the job is not a cron or interval job, it will return None.
    """
    if type(job.trigger) is not DateTrigger:
        pause_button: Button = _make_button("Pause", interactions.ButtonStyle.PRIMARY)
        unpause_button: Button = _make_button("Unpause", interactions.ButtonStyle.PRIMARY)

        if not hasattr(job, "next_run_time"):
            return pause_button

        return unpause_button if job.next_run_time is None else pause_button

    return None


def _get_row_of_buttons(job: Job) -> ActionRow:
    """Get components(buttons) for a page in /reminder list.

    These buttons are below the embed.

    Args:
        job: The job. Can be cron, interval or normal.

    Returns:
        ActionRow: A row of buttons.
    """
    components: list[Button] = [
        _make_button("Edit", interactions.ButtonStyle.PRIMARY),
        _make_button("Remove", interactions.ButtonStyle.DANGER),
    ]

    # Add pause/unpause button as the second button if it's a cron or interval job
    pause_or_unpause_button: Button | None = _get_pause_or_unpause_button(job=job)
    if pause_or_unpause_button is not None:
        components.insert(1, pause_or_unpause_button)

    # TODO: Should fix the type error
    return ActionRow(components=components)  # type: ignore  # noqa: PGH003


def _get_pages(job: Job, channel: Channel, ctx: CommandContext) -> Generator[Page, None, None]:
    """Get pages for a reminder.

    Args:
        job: The job. Can be cron, interval or normal.
        channel: Check if the job kwargs channel ID is the same as the channel ID we looped through.
        ctx: The context. Used to get the guild ID.

    Yields:
        Generator[Page, None, None]: A page.
    """
    # Get channel ID and guild ID from job kwargs
    channel_id: int = job.kwargs.get("channel_id")
    guild_id: int = job.kwargs.get("guild_id")

    if int(channel.id) == channel_id or ctx.guild_id == guild_id:
        message: str = job.kwargs.get("message")

        # If message is longer than 1000 characters, truncate it
        message = f"{message[:1000]}..." if len(message) > max_message_length else message

        # Create embed for the singular page
        embed: Embed = interactions.Embed(
            title=f"{job.id}",  # Example: 593dcc18aab748faa571017454669eae
            fields=[
                interactions.EmbedField(
                    name="**Channel:**",
                    value=f"#{channel.name}",  # Example: #general
                ),
                interactions.EmbedField(
                    name="**Message:**",
                    value=f"{message}",  # Example: Don't forget to feed the cat!
                ),
                interactions.EmbedField(
                    name="**Trigger:**",
                    value=_get_trigger_text(job=job),  # Example: 2023-08-24 00:06 (in 157 days, 23 hours, 49 minutes)
                ),
            ],
        )

        # Truncate title if it's longer than 90 characters
        # This is the text that shows up in the dropdown menu
        # Example: 2: Don't forget to feed the cat!
        dropdown_title: str = f"{message[:87]}..." if len(message) > max_title_length else message

        # Create a page and return it
        yield Page(
            embeds=embed,
            title=dropdown_title,
            components=_get_row_of_buttons(job),
            callback=_callback,
            position=RowPosition.BOTTOM,
        )


def _remove_job(job: Job) -> str:
    """Remove a job.

    Args:
        job: The job to remove.

    Returns:
        str: The message to send to Discord.
    """
    # TODO: Check if job exists before removing it?
    # TODO: Add button to undo the removal?
    channel_id: int = job.kwargs.get("channel_id")
    old_message: str = job.kwargs.get("message")
    try:
        trigger_time: datetime | str = job.trigger.run_date
    except AttributeError:
        trigger_time = "N/A"
    scheduler.remove_job(job.id)

    return f"Job {job.id} removed.\n**Message:** {old_message}\n**Channel:** {channel_id}\n**Time:** {trigger_time}"


def _unpause_job(job: Job, custom_scheduler: BaseScheduler = scheduler) -> str:
    """Unpause a job.

    Args:
        job: The job to unpause.
        custom_scheduler: The scheduler to use. Defaults to the global scheduler.

    Returns:
        str: The message to send to Discord.
    """
    # TODO: Should we check if the job is paused before unpause it?
    custom_scheduler.resume_job(job.id)
    return f"Job {job.id} unpaused."


def _pause_job(job: Job, custom_scheduler: BaseScheduler = scheduler) -> str:
    """Pause a job.

    Args:
        job: The job to pause.
        custom_scheduler: The scheduler to use. Defaults to the global scheduler.

    Returns:
        str: The message to send to Discord.
    """
    # TODO: Should we check if the job is unpaused before unpause it?
    custom_scheduler.pause_job(job.id)
    return f"Job {job.id} paused."


async def _callback(self: Paginator, ctx: ComponentContext) -> Message | None:
    """Callback for the paginator."""
    # TODO: Create a test for this
    if self.component_ctx is None or self.component_ctx.message is None:
        return await ctx.send("Something went wrong.", ephemeral=True)

    job_id: str | None = self.component_ctx.message.embeds[0].title
    job: Job | None = scheduler.get_job(job_id)

    if job is None:
        return await ctx.send("Job not found.", ephemeral=True)

    job.kwargs.get("channel_id")
    old_message: str = job.kwargs.get("message")

    components: list[TextInput] = [
        interactions.TextInput(
            style=interactions.TextStyleType.PARAGRAPH,
            label="New message",
            custom_id="new_message",
            value=old_message,
            required=False,
        ),
    ]

    job_type = "cron/interval"
    if type(job.trigger) is DateTrigger:
        # Get trigger time for normal reminders
        trigger_time: datetime | None = job.trigger.run_date
        job_type: str = "normal"
        components.append(
            interactions.TextInput(
                style=interactions.TextStyleType.SHORT,
                label="New date, Can be human readable or ISO8601",
                custom_id="new_date",
                value=str(trigger_time),
                required=False,
            ),
        )

    # Check what button was clicked and call the correct function
    msg = "Something went wrong. I don't know what you clicked."
    if ctx.custom_id == "edit":
        # TODO: Add buttons to increase/decrease hour
        modal: Modal = interactions.Modal(
            title=f"Edit {job_type} reminder.",
            custom_id="edit_modal",
            components=components,  # type: ignore  # noqa: PGH003
        )
        await ctx.popup(modal)
        msg = f"You modified {job_id}"
    elif ctx.custom_id == "pause":
        msg: str = _pause_job(job)
    elif ctx.custom_id == "unpause":
        msg: str = _unpause_job(job)
    elif ctx.custom_id == "remove":
        msg: str = _remove_job(job)

    return await ctx.send(msg, ephemeral=True)


async def create_pages(ctx: CommandContext) -> list[Page]:
    """Create pages for the paginator.

    Args:
        ctx: The context of the command.

    Returns:
        list[Page]: A list of pages.
    """
    # TODO: Add tests for this
    pages: list[Page] = []

    jobs: list[Job] = scheduler.get_jobs()
    for job in jobs:
        # Check if we're in a server
        if ctx.guild is None:
            await ctx.send("I can't find the server you're in. Are you sure you're in a server?", ephemeral=True)
            return []

        # Check if we're in a channel
        if ctx.guild.channels is None:
            await ctx.send("I can't find the channel you're in.", ephemeral=True)
            return []

        # Only add reminders from channels in the server we run "/reminder list" in
        # Check if channel is in the Discord server, if not, skip it.
        for channel in ctx.guild.channels:
            # Add a page for each reminder
            pages.extend(iter(_get_pages(job=job, channel=channel, ctx=ctx)))
    return pages
