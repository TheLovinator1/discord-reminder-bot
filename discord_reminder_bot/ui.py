from __future__ import annotations

import logging
import textwrap
from typing import TYPE_CHECKING

import discord
from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from discord.ui import Button, Select

from discord_reminder_bot import settings
from discord_reminder_bot.misc import calc_time, calculate
from discord_reminder_bot.parser import parse_time

if TYPE_CHECKING:
    import datetime

    from apscheduler.job import Job
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from discord_reminder_bot import settings


logger: logging.Logger = logging.getLogger(__name__)


class ModifyJobModal(discord.ui.Modal, title="Modify Job"):
    """Modal for modifying a job."""

    job_name = discord.ui.TextInput(label="Name", placeholder="Enter new job name")
    job_date = discord.ui.TextInput(label="Date", placeholder="Enter new job date")

    def __init__(self, job: Job, scheduler: AsyncIOScheduler) -> None:
        """Initialize the modify job modal.

        Args:
            job: The job to modify.
            scheduler: The scheduler to modify the job with.
        """
        super().__init__()
        self.job: Job = job
        self.scheduler: settings.AsyncIOScheduler = scheduler

        # Replace placeholders with current values
        self.job_name.label = self.get_job_name_label()
        self.job_date.label = f"Date ({self.job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')})"

        # Replace placeholders with current values
        self.job_name.placeholder = self.job.kwargs.get("message", "No message found")
        self.job_date.placeholder = self.job.next_run_time.strftime("%Y-%m-%d %H:%M:%S %Z")

        logger.info("Job '%s' Modal created", self.job.name)
        logger.info("\tCurrent date: '%s'", self.job.next_run_time)
        logger.info("\tCurrent message: '%s'", self.job.kwargs.get("message", "N/A"))

        logger.info("\tName label: '%s'", self.job_name.label)
        logger.info("\tDate label: '%s'", self.job_date.label)

    def get_job_name_label(self) -> str:
        """Get the job name label.

        Returns:
            str: The job name label.
        """
        label_max_chars: int = 45

        # If name is too long or not provided, use "Name" as label instead
        job_name_label: str = f"Name ({self.job.kwargs.get('message', 'X' * (label_max_chars + 1))})"

        if len(job_name_label) > label_max_chars:
            job_name_label = "Name"

        return job_name_label

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Submit the job modifications.

        Args:
            interaction: The interaction object for the command.
        """
        logger.info("Job '%s' modified: Submitting changes", self.job.name)
        new_name: str = self.job_name.value
        new_date_str: str = self.job_date.value
        old_date: datetime.datetime = self.job.next_run_time

        if new_date_str != old_date.strftime("%Y-%m-%d %H:%M:%S %Z"):
            new_date: datetime.datetime | None = parse_time(new_date_str)
            if not new_date:
                return await self.report_date_parsing_failure(
                    interaction=interaction,
                    new_date_str=new_date_str,
                    old_date=old_date,
                )

            await self.update_job_schedule(interaction, old_date, new_date)

        if self.job.name != new_name:
            await self.update_job_name(interaction, new_name)

        return None

    async def update_job_schedule(
        self,
        interaction: discord.Interaction,
        old_date: datetime.datetime,
        new_date: datetime.datetime,
    ) -> None:
        """Update the job schedule.

        Args:
            interaction: The interaction object for the command.
            old_date: The old date that was used.
            new_date: The new date to use.
        """
        logger.info("Job '%s' modified: New date: '%s'", self.job.name, new_date)
        logger.info("Job '%s' modified: Old date: '%s'", self.job.name, old_date)
        self.job.modify(next_run_time=new_date)

        old_date_str: str = old_date.strftime("%Y-%m-%d %H:%M:%S")
        new_date_str: str = new_date.strftime("%Y-%m-%d %H:%M:%S")

        await interaction.followup.send(
            content=(
                f"Job **{self.job.name}** was modified by {interaction.user.mention}:\n"
                f"Job ID: **{self.job.id}**\n"
                f"Old date: **{old_date_str}** {calculate(self.job)} {calc_time(old_date)}\n"
                f"New date: **{new_date_str}** {calculate(self.job)} {calc_time(new_date)}"
            ),
        )

    async def update_job_name(self, interaction: discord.Interaction, new_name: str) -> None:
        """Update the job name.

        Args:
            interaction: The interaction object for the command.
            new_name: The new name for the job.
        """
        logger.info("Job '%s' modified: New name: '%s'", self.job.name, new_name)
        logger.info("Job '%s' modified: Old name: '%s'", self.job.name, self.job.name)
        self.job.modify(name=new_name)

        await interaction.followup.send(
            content=(
                f"Job **{self.job.name}** was modified by {interaction.user.mention}:\n"
                f"Job ID: **{self.job.id}**\n"
                f"Old name: **{self.job.name}**\n"
                f"New name: **{new_name}**"
            ),
        )

    async def report_date_parsing_failure(
        self,
        interaction: discord.Interaction,
        new_date_str: str,
        old_date: datetime.datetime,
    ) -> None:
        """Report a date parsing failure.

        Args:
            interaction: The interaction object for the command.
            new_date_str: The new date string that failed to parse.
            old_date: The old date that was used instead.
        """
        logger.error("Job '%s' modified: Failed to parse date: '%s'", self.job.name, new_date_str)
        await self.on_error(
            interaction=interaction,
            error=ValueError(
                f"Got invalid date for job '{self.job.name}':\nJob ID: {self.job.id}\\Failed to parse date: {new_date_str}",  # noqa: E501
            ),
        )
        await interaction.followup.send(
            content=(
                f"Failed modifying job **{self.job.name}**\n"
                f"Job ID: **{self.job.id}**\n"
                f"Failed to parse date: **{new_date_str}**\n"
                f"Defaulting to old date: **{old_date.strftime('%Y-%m-%d %H:%M:%S')}** {calc_time(old_date)}"
            ),
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:  # noqa: PLR6301
        """Handle an error.

        Args:
            interaction: The interaction object for the command.
            error: The error that occurred.
        """
        await interaction.followup.send(f"An error occurred: {error}", ephemeral=True)


def create_job_embed(job: Job) -> discord.Embed:
    """Create an embed for a job.

    Args:
        job: The job to create the embed for.

    Returns:
        discord.Embed: The embed for the job.
    """
    next_run_time: datetime.datetime | str = (
        job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "Paused"
    )
    job_kwargs: dict = job.kwargs or {}
    channel_id: int = job_kwargs.get("channel_id", 0)
    message: str = job_kwargs.get("message", "N/A")
    author_id: int = job_kwargs.get("author_id", 0)
    embed_title: str = textwrap.shorten(f"{message}", width=256, placeholder="...")

    return discord.Embed(
        title=embed_title,
        description=f"ID: {job.id}\nNext run: {next_run_time}\nTime left: {calculate(job)}\nChannel: <#{channel_id}>\nAuthor: <@{author_id}>",  # noqa: E501
        color=discord.Color.blue(),
    )


class JobSelector(Select):
    """Select menu for selecting a job to manage."""

    def __init__(self, scheduler: AsyncIOScheduler) -> None:
        """Initialize the job selector.

        Args:
            scheduler: The scheduler to get the jobs from.
        """
        self.scheduler: settings.AsyncIOScheduler = scheduler
        options: list[discord.SelectOption] = []
        jobs: list[Job] = scheduler.get_jobs()

        # Only 25 options are allowed in a select menu.
        # TODO(TheLovinator): Add pagination for more than 25 jobs.  # noqa: TD003
        max_jobs: int = 25
        if len(jobs) > max_jobs:
            jobs = jobs[:max_jobs]

        for job in jobs:
            job_kwargs: dict = job.kwargs or {}

            label_prefix: str = ""
            if job.next_run_time is None:
                label_prefix = "Paused: "
            # Cron job
            elif isinstance(job.trigger, CronTrigger):
                label_prefix = "Cron: "
            # Interval job
            elif isinstance(job.trigger, IntervalTrigger):
                label_prefix = "Interval: "

            message: str = job_kwargs.get("message", f"{job.id}")
            message: str = textwrap.shorten(f"{label_prefix}{message}", width=100, placeholder="...")

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
            view = JobManagementView(job, self.scheduler)
            await interaction.response.edit_message(embed=embed, view=view)


class JobManagementView(discord.ui.View):
    """View for managing jobs."""

    def __init__(self, job: Job, scheduler: AsyncIOScheduler) -> None:
        """Initialize the job management view.

        Args:
            job: The job to manage.
            scheduler: The scheduler to manage the job with.
        """
        super().__init__(timeout=None)
        self.job: Job = job
        self.scheduler: settings.AsyncIOScheduler = scheduler
        self.add_item(JobSelector(scheduler))
        self.update_buttons()

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: Button) -> None:  # noqa: ARG002
        """Delete the job.

        Args:
            interaction: The interaction object for the command.
            button: The button that was clicked.
        """
        job_kwargs: dict = self.job.kwargs or {}

        logger.info("Deleting job: %s", self.job.id)
        if hasattr(self.job, "__getstate__"):
            logger.error("State: %s", self.job.__getstate__() if hasattr(self.job, "__getstate__") else "No state")

        # Log extra kwargs
        for key, value in job_kwargs.items():
            if key not in {"message", "channel_id", "author_id", "guild_id", "user_id"}:
                logger.error("Extra kwargs: %s: %s", key, value)

        msg: str = self.generate_deletion_message(job_kwargs)

        self.job.remove()
        await interaction.response.send_message(msg)
        self.stop()

    def generate_deletion_message(self, job_kwargs: dict[str, str | int]) -> str:  # noqa: C901, PLR0912
        """Generate the deletion message.

        Args:
            job_kwargs: The job kwargs.

        Returns:
            str: The deletion message.
        """
        msg: str = f"# Job *{job_kwargs.get('message'), 'No message'}* has been deleted.\n"
        msg += f"**Job ID**: {self.job.id}\n"

        # The time the job was supposed to run
        if hasattr(self.job, "next_run_time"):
            if self.job.next_run_time:
                msg += f"**Next run time**: ({self.job.next_run_time} {calculate(self.job)})\n"
            else:
                msg += "**Next run time**: Paused\n"
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

        msg += "\n## Debug info\n"

        # Callable (or a textual reference to one) to run at the given time
        if self.job.func:
            msg += f"**Function**: {self.job.func}\n"

        # Trigger that determines when func is called
        if self.job.trigger:
            msg += f"**Trigger**: {self.job.trigger}\n"

        # Alias of the executor to run the job with
        if self.job.executor:
            msg += f"**Executor**: {self.job.executor}\n"

        # List of positional arguments to call func with
        if self.job.args:
            msg += f"**Args**: {self.job.args}\n"

        # Textual description of the job
        if self.job.name:
            msg += f"**Name**: {self.job.name}\n"

        # Seconds after the designated runtime that the job is still allowed to be run (or None to allow the job to run no matter how late it is) # noqa: E501
        if self.job.misfire_grace_time:
            msg += f"**Misfire grace time**: {self.job.misfire_grace_time}\n"

        # Run once instead of many times if the scheduler determines that the job should be run more than once in succession # noqa: E501
        if self.job.coalesce:
            msg += f"**Coalesce**: {self.job.coalesce}\n"

        # Maximum number of concurrently running instances allowed for this job
        if self.job.max_instances:
            msg += f"**Max instances**: {self.job.max_instances}\n"

        return msg

    @discord.ui.button(label="Modify", style=discord.ButtonStyle.primary)
    async def modify_button(self, interaction: discord.Interaction, button: Button) -> None:  # noqa: ARG002
        """Modify the job.

        Args:
            interaction: The interaction object for the command.
            button: The button that was clicked.
        """
        logger.info("Modifying job: %s", self.job.id)
        if hasattr(self.job, "__getstate__"):
            logger.error("State: %s", self.job.__getstate__() if hasattr(self.job, "__getstate__") else "No state")

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
            status: str = f"What is this? {self.job.__getstate__()}"
            button.label = "What?"

        self.update_buttons()
        await interaction.response.edit_message(view=self)

        msg: str = f"Job '{self.job.name}' has been {status}."
        if hasattr(self.job, "next_run_time"):
            msg += f"\nNext run time: {self.job.next_run_time} {calculate(self.job)}"

        await interaction.followup.send(msg)

    def update_buttons(self) -> None:
        """Update the visibility of buttons based on job status."""
        self.pause_button.disabled = not self.job.next_run_time
        self.pause_button.label = "Resume" if self.job.next_run_time is None else "Pause"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:  # noqa: ARG002
        """Check the interaction and update buttons before responding.

        Args:
            interaction: The interaction object for the command.

        Returns:
            bool: Whether the interaction is valid.
        """
        self.update_buttons()
        return True
