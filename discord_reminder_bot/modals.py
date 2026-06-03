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


class _BaseReminderModifyModal(discord.ui.Modal):
    """Base modal for modifying a reminder job.

    Provides shared ``_update_message``, ``on_submit``, and ``on_error`` logic.
    Subclasses should override ``_get_additional_inputs`` to add trigger-specific
    form fields and ``_apply_trigger_changes`` to handle trigger-specific logic.
    """

    title = "Modify Reminder"

    def __init__(self, job: Job) -> None:
        """Initialize the base modal.

        Args:
            job: The APScheduler job to modify.
        """
        super().__init__()
        self.job = job
        self.job_id = job.id

        full_original_message: str = job.kwargs.get("message", "")
        self._full_original_message = full_original_message
        self.message_input = discord.ui.TextInput(
            label="Reminder message",
            default=full_original_message[:200],
            placeholder="Leave empty to keep current message",
            max_length=200,
            required=False,
        )

        self.add_item(self.message_input)
        self._add_trigger_inputs()

    def _add_trigger_inputs(self) -> None:
        """Add trigger-specific inputs to the modal.

        Override in subclasses to add additional form fields.
        """

    def _apply_trigger_changes(
        self,
        interaction: discord.Interaction,  # noqa: ARG002
    ) -> tuple[bool, str]:
        """Apply trigger-specific changes to the job.

        Override in subclasses to handle trigger-specific modification logic.

        Args:
            interaction: The Discord interaction that submitted the modal.

        Returns:
            tuple[bool, str]: Success flag and a message describing the changes (empty string if no changes).
        """
        return True, ""

    async def _update_message(self, old_message: str, new_message: str) -> bool:
        """Update the message of a job.

        Args:
            old_message: The old message.
            new_message: The new message.

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
        """Called when the modal is submitted.

        Args:
            interaction: The Discord interaction where this modal was triggered from.
        """
        old_message: str = self._full_original_message

        new_message: str = self.message_input.value or old_message

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

        msg: str = f"Modified job `{escape_markdown(self.job_id)}`:\n"
        changes_made = False

        # Apply trigger-specific changes
        trigger_success, trigger_msg = self._apply_trigger_changes(interaction)
        if not trigger_success:
            await interaction.followup.send(trigger_msg, ephemeral=True)
            return
        if trigger_msg:
            msg += trigger_msg
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
            interaction: The Discord interaction where this modal was triggered from.
            error: The raised exception.
        """
        if not interaction.response.is_done():
            await interaction.response.send_message("Oops! Something went wrong.", ephemeral=True)
        else:
            try:
                await interaction.followup.send("Oops! Something went wrong.", ephemeral=True)
            except discord.HTTPException:
                logger.warning("Failed to send error message via followup")

        logger.exception(f"Error in {self.__class__.__name__}")
        traceback.print_exception(type(error), error, error.__traceback__)


class DateReminderModifyModal(_BaseReminderModifyModal):
    """Modal for modifying a date-based APScheduler job (one-time reminder)."""

    def _add_trigger_inputs(self) -> None:
        """Add date/time input for date-based reminders."""
        self.time_input = discord.ui.TextInput(
            label="New time",
            placeholder="Leave empty to keep current time. e.g. tomorrow at 3 PM",
            required=False,
        )
        self.add_item(self.time_input)

    def _apply_trigger_changes(self, interaction: discord.Interaction) -> tuple[bool, str]:  # noqa: ARG002
        """Reschedule the date-based job.

        Args:
            interaction: The Discord interaction that submitted the modal.

        Returns:
            tuple[bool, str]: Success flag and message describing the schedule change.
        """
        new_time_str: str = self.time_input.value
        old_time: datetime.datetime | None = self.job.next_run_time
        old_time_countdown: str = calculate(self.job)

        # If time input is empty, keep the existing time
        if not new_time_str.strip():
            return True, ""  # No change to time

        parsed_time: datetime.datetime | None = parse_time(new_time_str)
        if not parsed_time:
            return False, f"Invalid time format: `{new_time_str}`"

        if old_time and parsed_time == old_time:
            return True, ""  # No change needed

        logger.info(f"Rescheduling date-based job {self.job_id}")
        try:
            rescheduled_job = scheduler.reschedule_job(self.job_id, trigger="date", run_date=parsed_time)
        except (ValueError, TypeError, AttributeError) as e:
            logger.exception("Failed to reschedule date-based job")
            return False, f"Failed to reschedule job: {e}"

        if old_time:
            msg: str = (
                f"Old time: `{old_time.strftime('%Y-%m-%d %H:%M:%S')}` (In {old_time_countdown})\n"
                f"New time: Next run in {calculate(rescheduled_job)}\n"
            )
        else:
            msg = f"Job unpaused. Next run in {calculate(rescheduled_job)}\n"
        return True, msg


class CronReminderModifyModal(_BaseReminderModifyModal):
    """Modal for modifying a cron-based reminder.

    Only the message can be edited through this modal due to UI limitations.
    """


class IntervalReminderModifyModal(_BaseReminderModifyModal):
    """Modal for modifying an interval-based reminder.

    Only the message can be edited through this modal due to UI limitations.
    """
