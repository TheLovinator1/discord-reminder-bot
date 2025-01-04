from __future__ import annotations

import logging
import textwrap
from typing import TYPE_CHECKING

import discord
from apscheduler.job import Job

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
