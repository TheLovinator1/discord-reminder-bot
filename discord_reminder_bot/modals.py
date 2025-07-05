from __future__ import annotations

import re
import traceback
from typing import TYPE_CHECKING

import discord
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from discord.utils import escape_markdown
from loguru import logger

from discord_reminder_bot.helpers import calculate, parse_time
from discord_reminder_bot.settings import scheduler

if TYPE_CHECKING:
    import datetime

    from apscheduler.job import Job


class ReminderModifyModal(discord.ui.Modal, title="Modify reminder"):
    """Modal for modifying a APScheduler job."""

    def __init__(self, job: Job) -> None:
        """Initialize the modal for modifying a reminder.

        Args:
            job (Job): The APScheduler job to modify.
        """
        super().__init__(title="Modify Reminder")
        self.job = job
        self.job_id = job.id
        self.trigger_type = self._get_trigger_type(job.trigger)

        self.message_input = discord.ui.TextInput(
            label="Reminder message",
            default=job.kwargs.get("message", ""),
            placeholder="What do you want to be reminded of?",
            max_length=200,
        )

        # Different input fields based on trigger type
        if self.trigger_type == "date":
            self.time_input = discord.ui.TextInput(
                label="New time",
                placeholder="e.g. tomorrow at 3 PM",
                required=True,
            )
        elif self.trigger_type == "interval":
            interval_text = self._format_interval_from_trigger(job.trigger)
            self.time_input = discord.ui.TextInput(
                label="New interval",
                placeholder="e.g. 1d 2h 30m (days, hours, minutes)",
                required=True,
                default=interval_text,
            )
        elif self.trigger_type == "cron":
            cron_text = self._format_cron_from_trigger(job.trigger)
            self.time_input = discord.ui.TextInput(
                label="New cron expression",
                placeholder="e.g. 0 9 * * 1-5 (min hour day month day_of_week)",
                required=True,
                default=cron_text,
            )
        else:
            # Fallback to date input for unknown trigger types
            self.time_input = discord.ui.TextInput(
                label="New time",
                placeholder="e.g. tomorrow at 3 PM",
                required=True,
            )

        self.add_item(self.message_input)
        self.add_item(self.time_input)

    def _get_trigger_type(self, trigger: DateTrigger | IntervalTrigger | CronTrigger) -> str:
        """Determine the type of trigger.

        Args:
            trigger: The APScheduler trigger.

        Returns:
            str: The type of trigger ("date", "interval", "cron", or "unknown").
        """
        if isinstance(trigger, DateTrigger):
            return "date"
        if isinstance(trigger, IntervalTrigger):
            return "interval"
        if isinstance(trigger, CronTrigger):
            return "cron"
        return "unknown"

    def _format_interval_from_trigger(self, trigger: IntervalTrigger) -> str:
        """Format an interval trigger into a human-readable string.

        Args:
            trigger (IntervalTrigger): The interval trigger.

        Returns:
            str: Formatted interval string (e.g., "1d 2h 30m").
        """
        parts = []

        # Get interval values from the trigger.__getstate__() dictionary
        trigger_state = trigger.__getstate__()

        if trigger_state.get("weeks", 0):
            parts.append(f"{trigger_state['weeks']}w")
        if trigger_state.get("days", 0):
            parts.append(f"{trigger_state['days']}d")
        if trigger_state.get("hours", 0):
            parts.append(f"{trigger_state['hours']}h")
        if trigger_state.get("minutes", 0):
            parts.append(f"{trigger_state['minutes']}m")

        seconds = trigger_state.get("seconds", 0)
        if seconds and seconds % 60 != 0:  # Only show seconds if not even minutes
            parts.append(f"{seconds % 60}s")

        return " ".join(parts) if parts else "0m"

    def _format_cron_from_trigger(self, trigger: CronTrigger) -> str:
        """Format a cron trigger into a string representation.

        Args:
            trigger (CronTrigger): The cron trigger.

        Returns:
            str: Formatted cron string.
        """
        fields = []

        # Get the fields in standard cron order
        for field in ["second", "minute", "hour", "day", "month", "day_of_week", "year"]:
            if hasattr(trigger, field) and getattr(trigger, field) is not None:
                expr = getattr(trigger, field).expression
                fields.append(expr if expr != "*" else "*")

        # Return only the standard 5 cron fields by default
        return " ".join(fields[:5])

    def _parse_interval_string(self, interval_str: str) -> dict[str, int]:
        """Parse an interval string into component parts.

        Args:
            interval_str (str): String like "1w 2d 3h 4m 5s"

        Returns:
            dict[str, int]: Dictionary with interval components.
        """
        interval_dict = {"weeks": 0, "days": 0, "hours": 0, "minutes": 0, "seconds": 0}

        # Define regex patterns for each time unit
        patterns = {r"(\d+)w": "weeks", r"(\d+)d": "days", r"(\d+)h": "hours", r"(\d+)m": "minutes", r"(\d+)s": "seconds"}

        # Extract values for each unit
        for pattern, key in patterns.items():
            match = re.search(pattern, interval_str)
            if match:
                interval_dict[key] = int(match.group(1))

        # Ensure at least 30 seconds total interval
        total_seconds = (
            interval_dict["weeks"] * 604800
            + interval_dict["days"] * 86400
            + interval_dict["hours"] * 3600
            + interval_dict["minutes"] * 60
            + interval_dict["seconds"]
        )

        if total_seconds < 30:
            interval_dict["seconds"] = 30

        return interval_dict

    def _parse_cron_string(self, cron_str: str) -> dict[str, str]:
        """Parse a cron string into its components.

        Args:
            cron_str (str): Cron string like "0 9 * * 1-5"

        Returns:
            dict[str, str]: Dictionary with cron components.
        """
        parts = cron_str.strip().split()
        cron_dict = {}

        # Map position to field name
        field_names = ["second", "minute", "hour", "day", "month", "day_of_week", "year"]

        # Handle standard 5-part cron string (minute hour day month day_of_week)
        if len(parts) == 5:
            # Add a 0 for seconds (as APScheduler expects it)
            parts.insert(0, "0")

        # Map parts to field names
        for i, part in enumerate(parts):
            if i < len(field_names) and part != "*":  # Only add non-default values
                cron_dict[field_names[i]] = part

        return cron_dict

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

    def _process_interval_trigger(self, new_time_str: str) -> tuple[bool, str, Job | None]:
        """Process interval trigger modification.

        Args:
            new_time_str (str): The new interval string to parse.

        Returns:
            tuple[bool, str, Job | None]: Success flag, error message, and rescheduled job.
        """
        try:
            interval_dict = self._parse_interval_string(new_time_str)
            logger.info(f"Rescheduling interval job {self.job_id} with {interval_dict}")
            rescheduled_job = scheduler.reschedule_job(self.job_id, trigger="interval", **interval_dict)
        except (ValueError, TypeError, AttributeError) as e:
            error_msg = f"Invalid interval format: `{new_time_str}`"
            logger.exception(f"Failed to parse interval: {e}")
            return False, error_msg, None
        else:
            return True, "", rescheduled_job

    def _process_cron_trigger(self, new_time_str: str) -> tuple[bool, str, Job | None]:
        """Process cron trigger modification.

        Args:
            new_time_str (str): The new cron string to parse.

        Returns:
            tuple[bool, str, Job | None]: Success flag, error message, and rescheduled job.
        """
        try:
            cron_dict = self._parse_cron_string(new_time_str)
            logger.info(f"Rescheduling cron job {self.job_id} with {cron_dict}")
            rescheduled_job = scheduler.reschedule_job(self.job_id, trigger="cron", **cron_dict)
        except (ValueError, TypeError, AttributeError) as e:
            error_msg = f"Invalid cron format: `{new_time_str}`"
            logger.exception(f"Failed to parse cron: {e}")
            return False, error_msg, None
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

        job = scheduler.get_job(self.job_id)
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

        # Process time/schedule changes based on trigger type
        success, error_msg, rescheduled_job = False, "", None

        if self.trigger_type == "date":
            success, error_msg, rescheduled_job = self._process_date_trigger(new_time_str, old_time)
        elif self.trigger_type == "interval":
            success, error_msg, rescheduled_job = self._process_interval_trigger(new_time_str)
        elif self.trigger_type == "cron":
            success, error_msg, rescheduled_job = self._process_cron_trigger(new_time_str)

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
        message_changed = await self._update_message(old_message, new_message)
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

        logger.exception(f"Error in ReminderModifyModal: {error}")
        traceback.print_exception(type(error), error, error.__traceback__)
