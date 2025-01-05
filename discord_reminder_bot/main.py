from __future__ import annotations

import logging
import textwrap
from typing import TYPE_CHECKING

import discord
from apscheduler.job import Job
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from discord.abc import PrivateChannel
from discord.ui import Button, Select
from discord_webhook import DiscordWebhook

from discord_reminder_bot import settings
from discord_reminder_bot.misc import calculate
from discord_reminder_bot.parser import parse_time
from discord_reminder_bot.ui import ModifyJobModal, create_job_embed

if TYPE_CHECKING:
    import datetime

    from apscheduler.job import Job
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

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

    @discord.app_commands.command(name="list", description="List, pause, unpause, and remove reminders.")
    async def list(self, interaction: discord.Interaction) -> None:  # noqa: PLR6301
        """List all reminders with pagination and buttons for deleting and modifying jobs.

        Args:
            interaction(discord.Interaction): The interaction object for the command.
        """
        await interaction.response.defer()

        jobs: list[Job] = settings.scheduler.get_jobs()
        if not jobs:
            await interaction.followup.send("No jobs available.")
            return

        first_job: Job | None = jobs[0] if jobs else None
        if not first_job:
            await interaction.followup.send("No jobs available.")
            return

        embed: discord.Embed = create_job_embed(first_job)
        view = JobManagementView(first_job, settings.scheduler)
        await interaction.followup.send(embed=embed, view=view)


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

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: Button) -> None:  # noqa: ARG002
        """Delete the job.

        Args:
            interaction: The interaction object for the command.
            button: The button that was clicked.
        """
        job_kwargs: dict = self.job.kwargs or {}

        logger.info("Deleting job: %s", self.job.id)
        logger.info("\tTrigger time: %s %s", self.job.next_run_time, calculate(self.job))
        logger.info("\tMessage: %s", self.job.kwargs.get("message", "N/A"))
        logger.info("\tChannel: <#%s>", self.job.kwargs.get("channel_id", 0))
        logger.info("\tCreated by: %s", self.job.kwargs.get("author_id", 0))
        logger.info("\tIn guild: %s", self.job.kwargs.get("guild_id", 0))
        logger.info("\tTo Discord user: %s", self.job.kwargs.get("user_id", 0))
        logger.info("\tFunction: %s", self.job.func)
        logger.info("\tTrigger: %s", self.job.trigger)
        logger.info("\tExecutor: %s", self.job.executor)
        logger.info("\tArgs: %s", self.job.args)
        logger.info("\tName: %s", self.job.name)
        logger.info("\tMisfire grace time: %s", self.job.misfire_grace_time)
        logger.info("\tCoalesce: %s", self.job.coalesce)
        logger.info("\tMax instances: %s", self.job.max_instances)

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
        modal = ModifyJobModal(self.job, self.scheduler)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Pause/Resume", style=discord.ButtonStyle.secondary)
    async def pause_button(self, interaction: discord.Interaction, button: Button) -> None:  # noqa: ARG002
        """Pause or resume the job.

        Args:
            interaction: The interaction object for the command.
            button: The button that was clicked.
        """
        if self.job.next_run_time is None:
            self.job.resume()
            status = "resumed"
        else:
            self.job.pause()
            status = "paused"
        await interaction.response.send_message(f"Job '{self.job.name}' has been {status}.", ephemeral=True)

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


if __name__ == "__main__":
    bot.run(settings.bot_token, root_logger=True)
