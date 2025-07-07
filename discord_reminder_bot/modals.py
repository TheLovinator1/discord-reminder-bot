from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

import discord
from discord.utils import escape_markdown
from loguru import logger

from discord_reminder_bot.helpers import calculate, parse_time
from discord_reminder_bot.settings import scheduler

if TYPE_CHECKING:
    import datetime

    from apscheduler.job import Job


class DateReminderModifyModal(discord.ui.Modal, title="Modify reminder"):
    """Modal for modifying a date-based APScheduler job (one-time reminder)."""

    def __init__(self, job: Job) -> None:
        """Initialize the modal for modifying a date-based reminder.

        Args:
            job (Job): The APScheduler job to modify. Must be a date-based job.
        """
        super().__init__(title="Modify Reminder")
        self.job = job
        self.job_id = job.id

        self.message_input = discord.ui.TextInput(
            label="Reminder message",
            default=job.kwargs.get("message", ""),
            placeholder="What do you want to be reminded of?",
            max_length=200,
        )

        # Only allow editing the date/time for date-based reminders
        self.time_input = discord.ui.TextInput(
            label="New time",
            placeholder="e.g. tomorrow at 3 PM",
            required=True,
        )

        self.add_item(self.message_input)
        self.add_item(self.time_input)

    def _process_date_trigger(self, new_time_str: str, old_time: datetime.datetime | None) -> tuple[bool, str, Job | None]:
        """Process date trigger modification.

        Args:
            new_time_str (str): The new time string to parse.
            old_time (datetime.datetime | None): The old scheduled time.

        Returns:
            tuple[bool, str, Job | None]: Success flag, error message, and rescheduled job.
        """
        parsed_time: datetime.datetime | None = parse_time(new_time_str)
        if not parsed_time:
            return False, f"Invalid time format: `{new_time_str}`", None

        if old_time and parsed_time == old_time:
            return True, "", None  # No change needed

        logger.info(f"Rescheduling date-based job {self.job_id}")
        try:
            rescheduled_job = scheduler.reschedule_job(self.job_id, trigger="date", run_date=parsed_time)
        except (ValueError, TypeError, AttributeError) as e:
            logger.exception(f"Failed to reschedule date-based job: {e}")
            return False, f"Failed to reschedule job: {e}", None
        else:
            return True, "", rescheduled_job

    async def _update_message(self, old_message: str, new_message: str) -> bool:
        """Update the message of a job.

        Args:
            old_message (str): The old message.
            new_message (str): The new message.

        Returns:
            bool: Whether the message was changed.
        """
        if new_message == old_message:
            return False

        job: Job | None = scheduler.get_job(self.job_id)
        if not job:
            return False

        old_kwargs = job.kwargs.copy()
        scheduler.modify_job(
            self.job_id,
            kwargs={
                **old_kwargs,
                "message": new_message,
            },
        )

        logger.debug(f"Modified job {self.job_id} with new message: {new_message}")
        logger.debug(f"Old kwargs: {old_kwargs}, New kwargs: {job.kwargs}")
        return True

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Called when the modal is submitted for a date-based reminder.

        Args:
            interaction (discord.Interaction): The Discord interaction where this modal was triggered from.
        """
        old_message: str = self.job.kwargs.get("message", "")
        old_time: datetime.datetime | None = self.job.next_run_time
        old_time_countdown: str = calculate(self.job)

        new_message: str = self.message_input.value
        new_time_str: str = self.time_input.value

        # Get the job to modify
        job_to_modify: Job | None = scheduler.get_job(self.job_id)
        if not job_to_modify:
            await interaction.response.send_message(
                f"Failed to get job.\n{new_message=}\n{new_time_str=}",
                ephemeral=True,
            )
            return

        # Defer early for long operations
        await interaction.response.defer(ephemeral=True)

        # Process date trigger
        success, error_msg, rescheduled_job = self._process_date_trigger(new_time_str, old_time)

        # If time input is invalid, send error message
        if not success and error_msg:
            await interaction.followup.send(error_msg, ephemeral=True)
            return

        # Update the message if changed
        msg: str = f"Modified job `{escape_markdown(self.job_id)}`:\n"
        changes_made = False

        # Add schedule change info to message
        if rescheduled_job:
            if old_time:
                msg += (
                    f"Old time: `{old_time.strftime('%Y-%m-%d %H:%M:%S')}` (In {old_time_countdown})\n"
                    f"New time: Next run in {calculate(rescheduled_job)}\n"
                )
            else:
                msg += f"Job unpaused. Next run in {calculate(rescheduled_job)}\n"
            changes_made = True

        # Update message if changed
        message_changed: bool = await self._update_message(old_message, new_message)
        if message_changed:
            msg += f"Old message: `{escape_markdown(old_message)}`\n"
            msg += f"New message: `{escape_markdown(new_message)}`.\n"
            changes_made = True

        # Send confirmation message
        if changes_made:
            await interaction.followup.send(content=msg)
        else:
            await interaction.followup.send(content=f"No changes made to job `{escape_markdown(self.job_id)}`.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """A callback that is called when on_submit fails with an error.

        Args:
            interaction (discord.Interaction): The Discord interaction where this modal was triggered from.
            error (Exception): The raised exception.
        """
        # Check if the interaction has already been responded to
        if not interaction.response.is_done():
            await interaction.response.send_message("Oops! Something went wrong.", ephemeral=True)
        else:
            try:
                await interaction.followup.send("Oops! Something went wrong.", ephemeral=True)
            except discord.HTTPException:
                logger.warning("Failed to send error message via followup")

        logger.exception(f"Error in {self.__class__.__name__}: {error}")
        traceback.print_exception(type(error), error, error.__traceback__)


class CronReminderModifyModal(discord.ui.Modal, title="Modify reminder"):
    """A modal for modifying a cron-based reminder."""

    def __init__(self, job: Job) -> None:
        """Initialize the modal for modifying a date-based reminder.

        Args:
            job (Job): The APScheduler job to modify. Must be a date-based job.
        """
        super().__init__(title="Modify Reminder")
        self.job = job
        self.job_id = job.id

        # message
        self.message_input = discord.ui.TextInput(
            label="Reminder message",
            default=job.kwargs.get("message", ""),
            placeholder="What do you want to be reminded of?",
            max_length=200,
        )

    async def _update_message(self, old_message: str, new_message: str) -> bool:
        """Update the message of a job.

        Args:
            old_message (str): The old message.
            new_message (str): The new message.

        Returns:
            bool: Whether the message was changed.
        """
        if new_message == old_message:
            return False

        job: Job | None = scheduler.get_job(self.job_id)
        if not job:
            return False

        old_kwargs = job.kwargs.copy()
        scheduler.modify_job(
            self.job_id,
            kwargs={
                **old_kwargs,
                "message": new_message,
            },
        )

        logger.debug(f"Modified job {self.job_id} with new message: {new_message}")
        logger.debug(f"Old kwargs: {old_kwargs}, New kwargs: {job.kwargs}")
        return True

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Called when the modal is submitted for a cron-based reminder.

        Args:
            interaction (discord.Interaction): The Discord interaction where this modal was triggered from.
        """
        old_message: str = self.job.kwargs.get("message", "")

        new_message: str = self.message_input.value

        # Get the job to modify
        job_to_modify: Job | None = scheduler.get_job(self.job_id)
        if not job_to_modify:
            await interaction.response.send_message(
                f"Failed to get job.\n{new_message=}",
                ephemeral=True,
            )
            return

        # Defer early for long operations
        await interaction.response.defer(ephemeral=True)

        # Update the message if changed
        msg: str = f"Modified job `{escape_markdown(self.job_id)}`:\n"
        changes_made = False

        # Update message if changed
        message_changed: bool = await self._update_message(old_message, new_message)
        if message_changed:
            msg += f"Old message: `{escape_markdown(old_message)}`\n"
            msg += f"New message: `{escape_markdown(new_message)}`.\n"
            changes_made = True

        # Send confirmation message
        if changes_made:
            await interaction.followup.send(content=msg)
        else:
            await interaction.followup.send(content=f"No changes made to job `{escape_markdown(self.job_id)}`.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """A callback that is called when on_submit fails with an error.

        Args:
            interaction (discord.Interaction): The Discord interaction where this modal was triggered from.
            error (Exception): The raised exception.
        """
        # Check if the interaction has already been responded to
        if not interaction.response.is_done():
            await interaction.response.send_message("Oops! Something went wrong.", ephemeral=True)
        else:
            try:
                await interaction.followup.send("Oops! Something went wrong.", ephemeral=True)
            except discord.HTTPException:
                logger.warning("Failed to send error message via followup")

        logger.exception(f"Error in {self.__class__.__name__}: {error}")
        traceback.print_exception(type(error), error, error.__traceback__)


class IntervalReminderModifyModal(discord.ui.Modal, title="Modify reminder"):
    """A modal for modifying an interval-based reminder."""

    def __init__(self, job: Job) -> None:
        """Initialize the modal for modifying a date-based reminder.

        Args:
            job (Job): The APScheduler job to modify. Must be a date-based job.
        """
        super().__init__(title="Modify Reminder")
        self.job = job
        self.job_id = job.id

        # message
        self.message_input = discord.ui.TextInput(
            label="Reminder message",
            default=job.kwargs.get("message", ""),
            placeholder="What do you want to be reminded of?",
            max_length=200,
        )

        self.add_item(self.message_input)

    async def _update_message(self, old_message: str, new_message: str) -> bool:
        """Update the message of a job.

        Args:
            old_message (str): The old message.
            new_message (str): The new message.

        Returns:
            bool: Whether the message was changed.
        """
        if new_message == old_message:
            return False

        job: Job | None = scheduler.get_job(self.job_id)
        if not job:
            return False

        old_kwargs = job.kwargs.copy()
        scheduler.modify_job(
            self.job_id,
            kwargs={
                **old_kwargs,
                "message": new_message,
            },
        )

        logger.debug(f"Modified job {self.job_id} with new message: {new_message}")
        logger.debug(f"Old kwargs: {old_kwargs}, New kwargs: {job.kwargs}")
        return True

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Called when the modal is submitted for an interval-based reminder.

        Args:
            interaction (discord.Interaction): The Discord interaction where this modal was triggered from.
        """
        old_message: str = self.job.kwargs.get("message", "")

        new_message: str = self.message_input.value

        # Get the job to modify
        job_to_modify: Job | None = scheduler.get_job(self.job_id)
        if not job_to_modify:
            await interaction.response.send_message(
                f"Failed to get job.\n{new_message=}",
                ephemeral=True,
            )
            return

        # Defer early for long operations
        await interaction.response.defer(ephemeral=True)

        # Update the message if changed
        msg: str = f"Modified job `{escape_markdown(self.job_id)}`:\n"
        changes_made = False

        # Update message if changed
        message_changed: bool = await self._update_message(old_message, new_message)
        if message_changed:
            msg += f"Old message: `{escape_markdown(old_message)}`\n"
            msg += f"New message: `{escape_markdown(new_message)}`.\n"
            changes_made = True

        # Send confirmation message
        if changes_made:
            await interaction.followup.send(content=msg)
        else:
            await interaction.followup.send(content=f"No changes made to job `{escape_markdown(self.job_id)}`.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """A callback that is called when on_submit fails with an error.

        Args:
            interaction (discord.Interaction): The Discord interaction where this modal was triggered from.
            error (Exception): The raised exception.
        """
        # Check if the interaction has already been responded to
        if not interaction.response.is_done():
            await interaction.response.send_message("Oops! Something went wrong.", ephemeral=True)
        else:
            try:
                await interaction.followup.send("Oops! Something went wrong.", ephemeral=True)
            except discord.HTTPException:
                logger.warning("Failed to send error message via followup")

        logger.exception(f"Error in {self.__class__.__name__}: {error}")
        traceback.print_exception(type(error), error, error.__traceback__)
