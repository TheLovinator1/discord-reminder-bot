from __future__ import annotations

import datetime
import json
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from apscheduler.job import Job
from discord.abc import PrivateChannel
from discord_webhook import DiscordWebhook

from discord_reminder_bot.misc import calculate
from discord_reminder_bot.parser import parse_time
from discord_reminder_bot.settings import get_bot_token, get_scheduler, get_webhook_url
from discord_reminder_bot.ui import JobManagementView, create_job_embed

if TYPE_CHECKING:
    from apscheduler.job import Job
    from discord.guild import GuildChannel
    from discord.interactions import InteractionChannel

    from discord_reminder_bot import settings

logger: logging.Logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

GUILD_ID = discord.Object(id=341001473661992962)

scheduler: settings.AsyncIOScheduler = get_scheduler()


class RemindBotClient(discord.Client):
    """Custom client class for the bot."""

    def __init__(self, *, intents: discord.Intents) -> None:
        """Initialize the bot client.

        Args:
            intents: The intents to use.
        """
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)

    async def on_ready(self) -> None:
        """Log when the bot is ready."""
        logger.info("Logged in as %s (%s)", self.user, self.user.id if self.user else "N/A ID")

    async def setup_hook(self) -> None:
        """Setup the bot."""
        scheduler.start()
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

                logger.info("\t%s: %s (%s)", msg[:50] or "No message", time, job.id)
        except Exception:
            logger.exception("Failed to loop through jobs")

        self.tree.copy_global_to(guild=GUILD_ID)
        await self.tree.sync(guild=GUILD_ID)


class RemindGroup(discord.app_commands.Group):
    """Group for remind commands."""

    def __init__(self) -> None:
        """Initialize the remind group."""
        super().__init__(name="remind", description="Group for remind commands")

    # /remind add
    @discord.app_commands.command(name="add", description="Add a new reminder")
    async def add(  # noqa: PLR0913, PLR0917, PLR6301
        self,
        interaction: discord.Interaction,
        message: str,
        time: str,
        channel: discord.TextChannel | None = None,
        user: discord.User | None = None,
        dm_and_current_channel: bool | None = None,  # noqa: FBT001
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
        # TODO(TheLovinator): Check if we have access to the channel and user # noqa: TD003
        await interaction.response.defer()

        logger.info("New reminder from %s (%s) in %s", interaction.user, interaction.user.id, interaction.channel)
        logger.info("Arguments: %s", {k: v for k, v in locals().items() if k != "self" and v is not None})

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
                job_kwargs={
                    "user_id": user.id,
                    "guild_id": guild.id,
                    "message": message,
                },
            )
            logger.info("User reminder job created: %s for %s at %s", user_reminder, user.id, time)

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
            job_kwargs={
                "channel_id": channel_id,
                "message": message,
                "author_id": interaction.user.id,
            },
        )
        logger.info("Channel reminder job created: %s for %s at %s", channel_job, channel_id, time)

        msg: str = (
            f"Hello {interaction.user.display_name},\n"
            f"I will notify you in <#{channel_id}>{dm_message}.\n"
            f"First run in {calculate(channel_job)} with the message:\n**{message}**."
        )

        await interaction.followup.send(content=msg)

    # /remind list
    @discord.app_commands.command(name="list", description="List, pause, unpause, and remove reminders.")
    async def list(self, interaction: discord.Interaction) -> None:  # noqa: PLR6301
        """List all reminders with pagination and buttons for deleting and modifying jobs.

        Args:
            interaction(discord.Interaction): The interaction object for the command.
        """
        await interaction.response.defer()

        jobs: list[Job] = scheduler.get_jobs()
        if not jobs:
            await interaction.followup.send(content="No scheduled jobs found in the database.", ephemeral=True)
            return

        embed: discord.Embed = create_job_embed(job=jobs[0])
        view = JobManagementView(job=jobs[0], scheduler=scheduler)

        await interaction.followup.send(embed=embed, view=view)

    # /remind cron
    @discord.app_commands.command(name="cron", description="Create new cron job. Works like UNIX cron.")
    async def cron(  # noqa: PLR0913, PLR0917, PLR6301
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
        dm_and_current_channel: bool | None = None,  # noqa: FBT001
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
        """  # noqa: E501
        try:
            await interaction.response.defer()
        except discord.HTTPException as e:
            logger.exception("Failed to defer interaction: text=%s, status=%s, code=%s", e.text, e.status, e.code)
            return
        except discord.InteractionResponded as e:
            logger.exception("Interaction already responded to - interaction: %s", e.interaction)
            return

        # Log kwargs
        logger.info("New cron job from %s (%s) in %s", interaction.user, interaction.user.id, interaction.channel)
        logger.info("Cron job arguments: %s", {k: v for k, v in locals().items() if k != "self" and v is not None})

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
    async def interval(  # noqa: PLR0913, PLR0917, PLR6301
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
        dm_and_current_channel: bool | None = None,  # noqa: FBT001
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
        """  # noqa: E501
        await interaction.response.defer()

        logger.info("New interval job from %s (%s) in %s", interaction.user, interaction.user.id, interaction.channel)
        logger.info("Arguments: %s", {k: v for k, v in locals().items() if k != "self" and v is not None})

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
    async def backup(self, interaction: discord.Interaction, all_servers: bool = False) -> None:  # noqa: FBT001, FBT002, PLR6301
        """Backup all reminders to a file.

        Args:
            interaction (discord.Interaction): The interaction object for the command.
            all_servers (bool): Backup all servers or just the current server. Defaults to only the current server.
        """
        await interaction.response.defer()

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
            logger.debug("Guild ID: %s, Channels in this guild: %s", guild_id, channels_in_this_guild)

            for job in jobs_data.get("jobs", []):
                # Check if the job is in the current guild
                job_guild_id = job.get("kwargs", {}).get("guild_id", 0)
                if job_guild_id and job_guild_id != guild_id:
                    logger.debug("Removing job: %s because it's not in the current guild. %s vs %s", job.get("id"), job_guild_id, guild_id)
                    jobs_data["jobs"].remove(job)

                # Check if the channel is in the current guild
                if job.get("kwargs", {}).get("channel_id") not in channels_in_this_guild:
                    logger.debug("Removing job: %s because it's not in the current guild's channels.", job.get("id"))
                    jobs_data["jobs"].remove(job)

        msg: str = "All reminders in this server have been backed up." if not all_servers else "All reminders have been backed up."
        msg += "\nYou can restore them using `/remind restore`."

        if not all_servers:
            msg += f"\nAmount of jobs on all servers: {amount_of_jobs}, in this server: {len(jobs_data.get('jobs', []))}"
            msg += "\nYou can use /remind backup all_servers:True to backup all servers."

        # Write the data to a new file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8", suffix=".json") as output_file:
            file_name = f"reminders-backup-{datetime.datetime.now(tz=scheduler.timezone)}.json"
            json.dump(jobs_data, output_file, indent=4)
            output_file.seek(0)

            await interaction.followup.send(content=msg, file=discord.File(output_file.name, filename=file_name))

    # /remind restore
    @discord.app_commands.command(name="restore", description="Restore reminders from a file.")
    async def restore(self, interaction: discord.Interaction) -> None:  # noqa: PLR6301
        """Restore reminders from a file.

        Args:
            interaction (discord.Interaction): The interaction object for the command.
        """
        await interaction.response.defer()

        logger.info("Restoring reminders from file for %s (%s) in %s", interaction.user, interaction.user.id, interaction.channel)

        # Get the old jobs
        old_jobs: list[Job] = scheduler.get_jobs()

        # Tell to reply with the file to this message
        await interaction.followup.send(content="Please reply to this message with the backup file.")

        while True:
            # Wait for the reply
            try:
                reply: discord.Message | None = await bot.wait_for("message", timeout=60, check=lambda m: m.author == interaction.user)
            except TimeoutError:
                # Modify the original message to say we timed out
                await interaction.edit_original_response(
                    content=("~~Please reply to this message with the backup file.~~\nTimed out after 60 seconds."),
                )
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
            logger.info("Saving attachment to %s", temp_file.name)
            await attachment.save(Path(temp_file.name))

            # Load the jobs data from the file
            temp_file.seek(0)
            jobs_data: dict = json.load(temp_file)

            logger.info("Importing jobs from file")
            logger.debug("Jobs data: %s", jobs_data)

            with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8", suffix=".json") as temp_import_file:
                # We can't import jobs with the same ID so remove them from the JSON
                jobs = [job for job in jobs_data.get("jobs", []) if not scheduler.get_job(job.get("id"))]
                jobs_already_exist = [job.get("id") for job in jobs_data.get("jobs", []) if scheduler.get_job(job.get("id"))]
                jobs_data["jobs"] = jobs
                for job_id in jobs_already_exist:
                    logger.debug("Removed job: %s because it already exists.", job_id)

                logger.debug("Jobs data after removing existing jobs: %s", jobs_data)
                logger.info("Jobs already exist: %s", jobs_already_exist)

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
            job_info: str = ""
            for j in added_jobs:
                job_info += f"\n• Message: {j.kwargs.get('message', 'No message found')} | Countdown: {calculate(j) or 'N/A'}"

            msg: str = f"Reminders restored successfully.\nAdded jobs:\n{job_info}"
            await interaction.followup.send(content=msg)
        else:
            await interaction.followup.send(content="No new reminders were added. Note that only jobs for this server will be restored.")


intents: discord.Intents = discord.Intents.default()
bot = RemindBotClient(intents=intents)

# Add the group to the bot
remind_group = RemindGroup()
bot.tree.add_command(remind_group)


def send_webhook(url: str = "", message: str = "") -> None:
    """Send a webhook to Discord.

    Args:
        url: Our webhook url, defaults to the one from settings.
        message: The message that will be sent to Discord.
    """
    if not message:
        logger.error("No message provided.")
        message = "No message provided."

    if not url:
        url = get_webhook_url()
        logger.error("No webhook URL provided. Using the one from settings.")
        webhook: DiscordWebhook = DiscordWebhook(
            url=url,
            username="discord-reminder-bot",
            content="No webhook URL provided. Using the one from settings.",
            rate_limit_retry=True,
        )
        webhook.execute()
        return

    webhook: DiscordWebhook = DiscordWebhook(url=url, content=message, rate_limit_retry=True)
    webhook.execute()


async def send_to_discord(channel_id: int, message: str, author_id: int) -> None:
    """Send a message to Discord.

    Args:
        channel_id: The Discord channel ID.
        message: The message.
        author_id: User we should ping.
    """
    channel: GuildChannel | discord.Thread | PrivateChannel | None = bot.get_channel(channel_id)
    if channel is None:
        channel = await bot.fetch_channel(channel_id)

    # Channels we can't send messages to
    if isinstance(channel, discord.ForumChannel | discord.CategoryChannel | PrivateChannel):
        logger.warning("We haven't implemented sending messages to this channel type (%s)", type(channel))
        return

    await channel.send(f"<@{author_id}>\n{message}")


async def send_to_user(user_id: int, guild_id: int, message: str) -> None:
    """Send a message to a user via DM.

    Args:
        user_id: The user ID to send the message to.
        guild_id: The guild ID to get the user from.
        message: The message to send.
    """
    # TODO(TheLovinator): Add try/except for all of these await calls  # noqa: TD003
    guild: discord.Guild | None = bot.get_guild(guild_id)
    if guild is None:
        guild = await bot.fetch_guild(guild_id)

    member: discord.Member | None = guild.get_member(user_id)
    if member is None:
        member = await guild.fetch_member(user_id)

    await member.send(message)


if __name__ == "__main__":
    bot_token: str = get_bot_token()
    bot.run(bot_token, root_logger=True)
