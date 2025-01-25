from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from discord.ui import Button, Select

from discord_reminder_bot.misc import DateTrigger, calc_time, calculate
from discord_reminder_bot.parser import parse_time

if TYPE_CHECKING:
    import datetime

    from apscheduler.job import Job
    from apscheduler.schedulers.asyncio import AsyncIOScheduler


logger: logging.Logger = logging.getLogger(__name__)


class ModifyJobModal(discord.ui.Modal, title="Modify Job"):
    """Modal for modifying a job."""

    job_name = discord.ui.TextInput(label="Name", placeholder="Enter new job name", required=False)
    job_date = discord.ui.TextInput(label="Date", placeholder="Enter new job date", required=False)

    def __init__(self, job: Job, scheduler: AsyncIOScheduler) -> None:
        """Initialize the modify job modal.

        Args:
            job: The job to modify.
            scheduler: The scheduler to modify the job with.
        """
        super().__init__()
        self.job: Job = job
        self.scheduler: AsyncIOScheduler = scheduler

        # Use "Name" as label if the message is too long, otherwise use the old message
        job_name_label: str = f"Name ({self.job.kwargs.get('message', 'X' * 46)})"
        if len(job_name_label) > 45:
            job_name_label = "Name"

        self.job_name.label = job_name_label
        self.job_date.label = f"Date ({self.job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')})"

        # Replace placeholders with current values
        self.job_name.placeholder = self.job.kwargs.get("message", "No message found")
        self.job_date.placeholder = self.job.next_run_time.strftime("%Y-%m-%d %H:%M:%S %Z")

        logger.info("Job '%s' Modal created", self.job.name)
        logger.info("\tCurrent date: '%s'", self.job.next_run_time)
        logger.info("\tCurrent message: '%s'", self.job.kwargs.get("message", "N/A"))

        logger.info("\tName label: '%s'", self.job_name.label)
        logger.info("\tDate label: '%s'", self.job_date.label)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Submit the job modifications.

        Args:
            interaction: The interaction object for the command.
        """
        logger.info("Job '%s' modified: Submitting changes", self.job.name)
        new_name: str = self.job_name.value
        new_date_str: str = self.job_date.value
        old_date: datetime.datetime = self.job.next_run_time

        # if both are empty, do nothing
        if not new_name and not new_date_str:
            logger.info("Job '%s' modified: No changes submitted", self.job.name)

            await interaction.response.send_message(
                content=f"Job **{self.job.name}** was not modified by {interaction.user.mention}.\nNo changes submitted.",
            )
            return

        if new_date_str and new_date_str != old_date.strftime("%Y-%m-%d %H:%M:%S %Z"):
            new_date: datetime.datetime | None = parse_time(new_date_str)
            if not new_date:
                logger.error("Job '%s' modified: Failed to parse date: '%s'", self.job.name, new_date_str)
                await interaction.response.send_message(
                    content=(
                        f"Failed modifying job **{self.job.name}**\n"
                        f"Job ID: **{self.job.id}**\n"
                        f"Failed to parse date: **{new_date_str}**\n"
                        f"Defaulting to old date: **{old_date.strftime('%Y-%m-%d %H:%M:%S')}** {calc_time(old_date)}"
                    ),
                )
                return

            logger.info("Job '%s' modified: New date: '%s'", self.job.name, new_date)
            logger.info("Job '%s' modified: Old date: '%s'", self.job.name, old_date)
            self.job.modify(next_run_time=new_date)

            old_date_str: str = old_date.strftime("%Y-%m-%d %H:%M:%S")
            new_date_str: str = new_date.strftime("%Y-%m-%d %H:%M:%S")

            await interaction.response.send_message(
                content=(
                    f"Job **{self.job.name}** was modified by {interaction.user.mention}:\n"
                    f"Job ID: **{self.job.id}**\n"
                    f"Old date: **{old_date_str}** {calculate(self.job)} {calc_time(old_date)}\n"
                    f"New date: **{new_date_str}** {calculate(self.job)} {calc_time(new_date)}"
                ),
            )

        if self.job_name.value and self.job.name != new_name:
            logger.info("Job '%s' modified: New name: '%s'", self.job.name, new_name)
            logger.info("Job '%s' modified: Old name: '%s'", self.job.name, self.job.name)
            self.job.modify(name=new_name)

            await interaction.response.send_message(
                content=(
                    f"Job **{self.job.name}** was modified by {interaction.user.mention}:\n"
                    f"Job ID: **{self.job.id}**\n"
                    f"Old name: **{self.job.name}**\n"
                    f"New name: **{new_name}**"
                ),
            )


def create_job_embed(job: Job) -> discord.Embed:
    """Create an embed for a job.

    Args:
        job: The job to create the embed for.

    Returns:
        discord.Embed: The embed for the job.
    """
    job_kwargs: dict = job.kwargs or {}
    channel_id: int = job_kwargs.get("channel_id", 0)
    message: str = job_kwargs.get("message", "N/A")
    author_id: int = job_kwargs.get("author_id", 0)
    embed_title: str = f"{message[:256]}..." if len(message) > 256 else message

    msg: str = f"ID: {job.id}\n"
    if hasattr(job, "next_run_time"):
        if job.next_run_time:
            msg += f"Next run: {job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        else:
            msg += "Paused\n"
    if isinstance(job.trigger, IntervalTrigger):
        msg += f"Interval: {job.trigger.interval}"
    if channel_id:
        msg += f"Channel: <#{channel_id}>\n"
    if author_id:
        msg += f"Author: <@{author_id}>"

    return discord.Embed(title=embed_title, description=msg, color=discord.Color.blue())


class JobSelector(Select):
    """Select menu for selecting a job to manage."""

    def __init__(self, scheduler: AsyncIOScheduler, guild: discord.Guild) -> None:
        """Initialize the job selector.

        Args:
            scheduler: The scheduler to get the jobs from.
            guild: The guild this view is for.
        """
        self.scheduler: AsyncIOScheduler = scheduler
        self.guild: discord.Guild = guild

        options: list[discord.SelectOption] = []
        jobs: list[Job] = scheduler.get_jobs()

        jobs_in_guild: list[Job] = []
        list_of_channels_in_current_guild: list[int] = [c.id for c in guild.channels]
        for job in jobs:
            # If the job has guild_id and it's not the current guild, skip it
            if job.kwargs.get("guild_id") and job.kwargs.get("guild_id") != guild.id:
                logger.debug("Skipping job: %s because it's not in the current guild.", job.id)
                continue

            # If the job has channel_id and it's not in the current guild, skip it
            if job.kwargs.get("channel_id") and job.kwargs.get("channel_id") not in list_of_channels_in_current_guild:
                logger.debug("Skipping job: %s because it's not in the current guild's channels.", job.id)
                continue

            jobs_in_guild.append(job)

        # Only 25 options are allowed in a select menu.
        # TODO(TheLovinator): Add pagination for more than 25 jobs.  # noqa: TD003
        max_jobs: int = 25
        if len(jobs_in_guild) > max_jobs:
            jobs_in_guild = jobs_in_guild[:max_jobs]

        for job in jobs_in_guild:
            label_prefix: str = ""
            label_prefix = "Paused: " if job.next_run_time is None else label_prefix
            label_prefix = "Interval: " if isinstance(job.trigger, IntervalTrigger) else label_prefix
            label_prefix = "Cron: " if isinstance(job.trigger, CronTrigger) else label_prefix

            job_kwargs: dict = job.kwargs or {}
            message: str = job_kwargs.get("message", f"{job.id}")
            message = f"{label_prefix}{message}"
            message = message[:96] + "..." if len(message) > 100 else message

            options.append(discord.SelectOption(label=message, value=job.id))

        super().__init__(placeholder="Select a job...", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Callback for the job selector.

        Args:
            interaction: The interaction object for the command.
        """
        job: Job | None = self.scheduler.get_job(self.values[0])
        if job:
            embed: discord.Embed = create_job_embed(job)
            view = JobManagementView(job, self.scheduler, guild=self.guild)
            await interaction.response.edit_message(embed=embed, view=view)


class JobManagementView(discord.ui.View):
    """View for managing jobs."""

    def __init__(self, job: Job, scheduler: AsyncIOScheduler, guild: discord.Guild) -> None:
        """Initialize the job management view.

        Args:
            job: The job to manage.
            scheduler: The scheduler to manage the job with.
            guild: The guild this view is for.
        """
        super().__init__(timeout=None)
        self.job: Job = job
        self.scheduler: AsyncIOScheduler = scheduler
        self.guild: discord.Guild = guild

        self.add_item(JobSelector(scheduler, self.guild))
        self.update_buttons()

        logger.debug("JobManagementView created for job: %s", job.id)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: Button) -> None:  # noqa: ARG002
        """Delete the job.

        Args:
            interaction: The interaction object for the command.
            button: The button that was clicked.
        """
        job_kwargs: dict = self.job.kwargs or {}

        logger.info("Deleting job: %s because %s clicked the button.", self.job.id, interaction.user.name)
        if hasattr(self.job, "__getstate__"):
            logger.debug("State: %s", self.job.__getstate__() if hasattr(self.job, "__getstate__") else "No state")

        job_msg: str | int = job_kwargs.get("message", "No message found")
        msg: str = f"**Job '{job_msg}' has been deleted.**\n"
        msg += f"**Job ID**: {self.job.id}\n"

        # The time the job was supposed to run
        if hasattr(self.job, "next_run_time"):
            if self.job.next_run_time:
                msg += f"**Next run time**: {self.job.next_run_time} ({calculate(self.job)})\n"
            else:
                msg += "**Next run time**: Paused\n"
                msg += f"**Trigger**: {self.job.trigger}\n"
        else:
            msg += "**Next run time**: Pending\n"

        # The Discord user who created the job
        if job_kwargs.get("author_id"):
            msg += f"**Created by**: <@{job_kwargs.get('author_id')}>\n"

        # The Discord channel to send the message to
        if job_kwargs.get("channel_id"):
            msg += f"**Channel**: <#{job_kwargs.get('channel_id')}>\n"

        # The Discord user to send the message to
        if job_kwargs.get("user_id"):
            msg += f"**User**: <@{job_kwargs.get('user_id')}>\n"

        # The Discord guild to send the message to
        if job_kwargs.get("guild_id"):
            msg += f"**Guild**: {job_kwargs.get('guild_id')}\n"

        logger.debug("Deletion message: %s", msg)

        self.job.remove()
        await interaction.response.send_message(msg)
        self.stop()

    @discord.ui.button(label="Modify", style=discord.ButtonStyle.primary)
    async def modify_button(self, interaction: discord.Interaction, button: Button) -> None:  # noqa: ARG002
        """Modify the job.

        Args:
            interaction: The interaction object for the command.
            button: The button that was clicked.
        """
        logger.info("Modifying job: %s. Clicked by %s", self.job.id, interaction.user.name)
        if hasattr(self.job, "__getstate__"):
            logger.debug("State: %s", self.job.__getstate__() if hasattr(self.job, "__getstate__") else "No state")

        modal = ModifyJobModal(self.job, self.scheduler)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Pause/Resume", style=discord.ButtonStyle.secondary)
    async def pause_button(self, interaction: discord.Interaction, button: Button) -> None:
        """Pause or resume the job.

        Args:
            interaction: The interaction object for the command.
            button: The button that was clicked.
        """
        if hasattr(self.job, "next_run_time"):
            if self.job.next_run_time is None:
                logger.info("State: %s", self.job.__getstate__())
                self.job.resume()
                status = "resumed"
                button.label = "Pause"
            else:
                logger.info("State: %s", self.job.__getstate__())
                self.job.pause()
                status = "paused"
                button.label = "Resume"
        else:
            logger.error("Got a job without a next_run_time: %s", self.job.id)
            status: str = f"What is this? {self.job.__getstate__()}"
            button.label = "What?"

        self.update_buttons()
        await interaction.response.edit_message(view=self)

        job_kwargs: dict = self.job.kwargs or {}
        job_msg: str = job_kwargs.get("message", "No message found")
        job_author: int = job_kwargs.get("author_id", 0)
        msg: str = f"Job '{job_msg}' has been {status} by <@{interaction.user.id}>. Job was created by <@{job_author}>."

        if hasattr(self.job, "next_run_time"):
            trigger_time: datetime.datetime | None = (
                self.job.trigger.run_date if isinstance(self.job.trigger, DateTrigger) else self.job.next_run_time
            )
            msg += f"\nNext run time: {trigger_time} {calculate(self.job)}"

        await interaction.followup.send(msg)

    def update_buttons(self) -> None:
        """Update the visibility of buttons based on job status."""
        logger.debug("Updating buttons for job: %s", self.job.id)
        self.pause_button.label = "Resume" if self.job.next_run_time is None else "Pause"

        logger.debug("Pause button disabled: %s", self.pause_button.disabled)
        logger.debug("Pause button label: %s", self.pause_button.label)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:  # noqa: ARG002
        """Check the interaction and update buttons before responding.

        Args:
            interaction: The interaction object for the command.

        Returns:
            bool: Whether the interaction is valid.
        """
        self.update_buttons()
        return True
