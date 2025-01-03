from __future__ import annotations

import datetime
import logging
from zoneinfo import ZoneInfo

import dateparser
import discord
from discord.abc import PrivateChannel
from discord_webhook import DiscordWebhook

from discord_reminder_bot import settings

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


def parse_time(date_to_parse: str, timezone: str | None = None) -> datetime.datetime | None:
    """Parse a date string into a datetime object.

    Args:
        date_to_parse(str): The date string to parse.
        timezone(str, optional): The timezone to use. Defaults timezone from settings.

    Returns:
        datetime.datetime: The parsed datetime object.
    """
    logger.info("Parsing date: '%s' with timezone: '%s'", date_to_parse, timezone)

    if not date_to_parse:
        logger.error("No date provided to parse.")
        return None

    if not timezone:
        timezone = settings.config_timezone

    parsed_date: datetime.datetime | None = dateparser.parse(
        date_string=date_to_parse,
        settings={
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": f"{timezone}",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "RELATIVE_BASE": datetime.datetime.now(tz=ZoneInfo(timezone)),
        },
    )

    return parsed_date


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
        await interaction.response.defer()
        self.log_reminder_details(interaction, message, time, channel, user, dm_and_current_channel)
        return await self.parse_reminder_time(interaction, time)

    @staticmethod
    async def parse_reminder_time(interaction: discord.Interaction, time: str) -> None:
        """Parse the reminder time.

        Args:
            interaction: The interaction object for the command.
            time: The time of the reminder.
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
            return
        await interaction.followup.send(f"Reminder set for {parsed}")

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

    @discord.app_commands.command(name="list", description="List all reminders")
    async def list(self, interaction: discord.Interaction) -> None:  # noqa: PLR6301
        """List all reminders.

        Args:
            interaction: The interaction.
        """
        reminders: list[str] = ["Meeting at 10 AM", "Lunch at 12 PM"]
        reminder_text: str = "\n".join(reminders)
        await interaction.response.send_message(f"Your reminders:\n{reminder_text}")


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
