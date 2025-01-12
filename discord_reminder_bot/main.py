from __future__ import annotations

import logging
from pprint import pformat
from typing import TYPE_CHECKING

import discord
from apscheduler.job import Job
from discord.abc import PrivateChannel
from discord_webhook import DiscordWebhook

from discord_reminder_bot import settings
from discord_reminder_bot.misc import calculate
from discord_reminder_bot.parser import parse_time
from discord_reminder_bot.ui import JobManagementView, create_job_embed

if TYPE_CHECKING:
    import datetime
    from collections.abc import Callable

    from apscheduler.job import Job

logger: logging.Logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

GUILD_ID = discord.Object(id=341001473661992962)


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
        settings.scheduler.start()
        log_current_jobs()

        try:
            self.tree.copy_global_to(guild=GUILD_ID)
            await self.tree.sync(guild=GUILD_ID)
        except discord.app_commands.CommandSyncFailure:
            exp_msg = "Syncing the commands failed due to a user related error, typically because the command has invalid data. This is equivalent to an HTTP status code of 400."  # noqa: E501
            logger.exception(exp_msg)
        except discord.Forbidden:
            logger.exception("The client does not have the applications.commands scope in the guild.")
        except discord.app_commands.MissingApplicationID:
            logger.exception("The client does not have an application ID.")
        except discord.app_commands.TranslationError:
            logger.exception("An error occurred while translating the commands.")
        except discord.HTTPException as e:
            logger.exception("An HTTP error occurred: %s, %s, %s", e.text, e.status, e.code)


class RemindGroup(discord.app_commands.Group):
    """Group for remind commands."""

    def __init__(self) -> None:
        """Initialize the remind group."""
        super().__init__(name="remind", description="Group for remind commands")

    # /remind add
    @discord.app_commands.command(name="add", description="Add a new reminder")
    async def add(  # noqa: PLR0913, PLR0917
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
        """  # noqa: E501
        # TODO(TheLovinator): Add try/except for all of these await calls  # noqa: TD003
        # TODO(TheLovinator): Add a warning if the interval is too short  # noqa: TD003
        # TODO(TheLovinator): Check if we have access to the channel and user# noqa: TD003

        should_send_channel_reminder = True

        await interaction.response.defer()
        self.log_reminder_details(interaction, message, time, channel, user, dm_and_current_channel)
        parsed_time: datetime.datetime | None = await self.parse_reminder_time(interaction, time)
        if not parsed_time:
            return

        run_date: str = parsed_time.strftime("%Y-%m-%d %H:%M:%S")
        guild: discord.Guild | None = interaction.guild or None
        if not guild:
            await interaction.followup.send("Failed to get guild.")
            return

        dm_message: str = ""
        where_and_when = ""
        channel_id: int | None = self.get_channel_id(interaction, channel)
        if user:
            user_reminder: Job = settings.scheduler.add_job(
                send_to_user,
                run_date=run_date,
                kwargs={
                    "user_id": user.id,
                    "guild_id": guild.id,
                    "message": message,
                },
            )

            dm_message = f"and a DM to {user.display_name} "
            if not dm_and_current_channel:
                should_send_channel_reminder = False
                where_and_when: str = (
                    f"I will send a DM to {user.display_name} at:\n**{run_date}** {calculate(user_reminder)}\n"
                )
        if should_send_channel_reminder:
            reminder: Job = settings.scheduler.add_job(
                send_to_discord,
                run_date=run_date,
                kwargs={
                    "channel_id": channel_id,
                    "message": message,
                    "author_id": interaction.user.id,
                },
            )
            where_and_when = (
                f"I will notify you in <#{channel_id}> {dm_message}at:\n**{run_date}** {calculate(reminder)}\n"
            )
        final_message: str = f"Hello {interaction.user.display_name}, {where_and_when}With the message:\n**{message}**."
        await interaction.followup.send(final_message)

    # /remind list
    @discord.app_commands.command(name="list", description="List, pause, unpause, and remove reminders.")
    async def list(self, interaction: discord.Interaction) -> None:  # noqa: PLR6301
        """List all reminders with pagination and buttons for deleting and modifying jobs.

        Args:
            interaction(discord.Interaction): The interaction object for the command.
        """
        await interaction.response.defer()

        jobs: list[Job] = settings.scheduler.get_jobs()
        if not jobs:
            await interaction.followup.send(content="No jobs available.")
            return

        first_job: Job | None = jobs[0] if jobs else None
        if not first_job:
            await interaction.followup.send(content="No jobs available.")
            return

        embed: discord.Embed = create_job_embed(job=first_job)
        view = JobManagementView(job=first_job, scheduler=settings.scheduler)
        await interaction.followup.send(embed=embed, view=view)

    # /remind cron
    @discord.app_commands.command(name="cron", description="Create new cron job. Works like UNIX cron.")
    async def cron(  # noqa: PLR0913, PLR0917
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
        # TODO(TheLovinator): Add try/except for all of these await calls  # noqa: TD003
        # TODO(TheLovinator): Add a warning if the interval is too short  # noqa: TD003
        # TODO(TheLovinator): Check if we have access to the channel and user# noqa: TD003

        # Log kwargs
        logger.info("New cron job from %s (%s) in %s", interaction.user, interaction.user.id, interaction.channel)
        logger.info("Cron job arguments: %s", {k: v for k, v in locals().items() if k != "self" and v is not None})

        # Get the channel ID
        channel_id: int | None = self.get_channel_id(interaction=interaction, channel=channel)
        if not channel_id:
            await interaction.followup.send(content="Failed to get channel.")
            return

        # Ensure the guild is valid
        guild: discord.Guild | None = interaction.guild or None
        if not guild:
            await interaction.followup.send(content="Failed to get guild.")
            return

        # Helper to add a job
        def add_job(func: Callable, job_kwargs: dict[str, int | str]) -> Job:
            return settings.scheduler.add_job(
                func=func,
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
                kwargs=job_kwargs,
            )

        # Create user DM reminder job if user is specified
        dm_message: str = ""
        if user:
            dm_job: Job = add_job(
                func=send_to_user,
                job_kwargs={
                    "user_id": user.id,
                    "guild_id": guild.id,
                    "message": message,
                },
            )
            dm_message = f" and a DM to {user.display_name}"
            if not dm_and_current_channel:
                # If only DM is required, notify about the DM job and exit
                await interaction.followup.send(
                    content=f"Hello {interaction.user.display_name},\n"
                    f"I will send a DM to {user.display_name} at:\n"
                    f"First run in {calculate(dm_job)} with the message:\n**{message}**.",
                )

        # Create channel reminder job
        channel_job: Job = add_job(
            func=send_to_discord,
            job_kwargs={
                "channel_id": channel_id,
                "message": message,
                "author_id": interaction.user.id,
            },
        )

        # Compose the final message
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
    async def interval(  # noqa: PLR0913, PLR0917
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
        # TODO(TheLovinator): Add try/except for all of these await calls  # noqa: TD003
        # TODO(TheLovinator): Add a warning if the interval is too short  # noqa: TD003
        # TODO(TheLovinator): Check if we have access to the channel and user# noqa: TD003

        logger.info("New interval job from %s (%s) in %s", interaction.user, interaction.user.id, interaction.channel)
        logger.info("Interval job arguments: %s", {k: v for k, v in locals().items() if k != "self" and v is not None})

        # Get the channel ID
        channel_id: int | None = self.get_channel_id(interaction=interaction, channel=channel)
        if not channel_id:
            await interaction.followup.send(content="Failed to get channel.")
            return

        # Ensure the guild is valid
        guild: discord.Guild | None = interaction.guild or None
        if not guild:
            await interaction.followup.send(content="Failed to get guild.")
            return

        # Helper to add a job
        def add_job(func: Callable, job_kwargs: dict[str, int | str]) -> Job:
            return settings.scheduler.add_job(
                func=func,
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
                kwargs=job_kwargs,
            )

        # Create user DM reminder job if user is specified
        dm_message: str = ""
        if user:
            dm_job: Job = add_job(
                func=send_to_user,
                job_kwargs={
                    "user_id": user.id,
                    "guild_id": guild.id,
                    "message": message,
                },
            )
            dm_message = f" and a DM to {user.display_name} "
            if not dm_and_current_channel:
                # If only DM is required, notify about the DM job and exit
                await interaction.followup.send(
                    content=f"Hello {interaction.user.display_name},\n"
                    f"I will send a DM to {user.display_name} at:\n"
                    f"First run in {calculate(dm_job)} with the message:\n**{message}**.",
                )

        # Create channel reminder job
        channel_job: Job = add_job(
            func=send_to_discord,
            job_kwargs={
                "channel_id": channel_id,
                "message": message,
                "author_id": interaction.user.id,
            },
        )

        # Compose the final message
        await interaction.followup.send(
            content=f"Hello {interaction.user.display_name},\n"
            f"I will notify you in <#{channel_id}>{dm_message}.\n"
            f"First run in {calculate(channel_job)} with the message:\n**{message}**.",
        )

    @staticmethod
    def get_channel_id(interaction: discord.Interaction, channel: discord.TextChannel | None) -> int | None:
        """Get the channel ID to send the reminder to.

        Args:
            interaction: The interaction object for the command.
            channel: The channel to send the reminder to.

        Returns:
            int: The channel ID to send the reminder to.
        """
        channel_id: int | None = None
        if interaction.channel:
            channel_id = interaction.channel.id
        if channel:
            logger.info("Channel provided: %s (%s) so using that instead of current channel.", channel, channel.id)
            channel_id = channel.id
        logger.info("Will send reminder to channel: %s (%s)", channel, channel_id)

        return channel_id

    @staticmethod
    async def parse_reminder_time(interaction: discord.Interaction, time: str) -> datetime.datetime | None:
        """Parse the reminder time.

        Args:
            interaction: The interaction object for the command.
            time: The time of the reminder.

        Returns:
            datetime.datetime: The parsed time.
        """
        parsed = None
        error_during_parsing: ValueError | TypeError | None = None
        try:
            parsed: datetime.datetime | None = parse_time(date_to_parse=time)
        except (ValueError, TypeError) as e:
            logger.exception("Error parsing time '%s'", time)
            error_during_parsing = e
        if not parsed:
            await interaction.followup.send(f"Failed to parse time. Error: {error_during_parsing}")
            return None
        return parsed

    @staticmethod
    def log_reminder_details(  # noqa: PLR0913, PLR0917
        interaction: discord.Interaction,
        message: str,
        time: str,
        channel: discord.TextChannel | None,
        user: discord.User | None,
        dm_and_current_channel: bool | None,  # noqa: FBT001
    ) -> None:
        """Log the details of the reminder.

        Args:
            interaction: The interaction object for the command.
            message: The content of the reminder.
            time: The time of the reminder.
            channel: The channel to send the reminder to.
            user: Send reminder as a DM to this user.
            dm_and_current_channel: Send reminder as a DM to the user and in this channel.
        """
        logger.info("New reminder from %s (%s) in %s", interaction.user, interaction.user.id, interaction.channel)
        logger.info("Adding reminder: %s Time: %s", message, time)
        logger.info("Channel: %s User: %s", channel, user)
        logger.info("DM and current channel: %s", dm_and_current_channel)


intents: discord.Intents = discord.Intents.default()
bot = RemindBotClient(intents=intents)

# Add the group to the bot
remind_group = RemindGroup()
bot.tree.add_command(remind_group)


def send_webhook(
    url: str = settings.webhook_url,
    message: str = "discord-reminder-bot: Empty message.",
) -> None:
    """Send a webhook to Discord.

    Args:
        url: Our webhook url, defaults to the one from settings.
        message: The message that will be sent to Discord.
    """
    if not url:
        msg = "ERROR: Tried to send a webhook but you have no webhook url configured."
        logger.error(msg)
        webhook: DiscordWebhook = DiscordWebhook(url=settings.webhook_url, content=msg, rate_limit_retry=True)
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
    # TODO(TheLovinator): Add try/except for all of these await calls  # noqa: TD003
    channel: (
        discord.VoiceChannel
        | discord.StageChannel
        | discord.ForumChannel
        | discord.TextChannel
        | discord.CategoryChannel
        | discord.Thread
        | PrivateChannel
        | None
    ) = bot.get_channel(channel_id)
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


def log_current_jobs() -> None:
    """Log the current jobs."""
    jobs: list[Job] = settings.scheduler.get_jobs()
    if not jobs:
        logger.info("No jobs available.")
        return

    for job in jobs:
        logger.debug("Job: %s", job)

        state = {} if not hasattr(job, "__getstate__") else job.__getstate__()
        if state:
            logger.debug("State:\n%s", pformat(state))


if __name__ == "__main__":
    bot.run(settings.bot_token, root_logger=True)
