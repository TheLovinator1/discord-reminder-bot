from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

import hikari
import lightbulb
from discord_webhook import DiscordWebhook
from loguru import logger

from discord_reminder_bot import cmd_add
from discord_reminder_bot.settings import bot_token, webhook_url

if TYPE_CHECKING:
    from requests import Response

intents: hikari.Intents = hikari.Intents.GUILD_MESSAGES | hikari.Intents.DM_MESSAGES
bot = lightbulb.BotApp(token=bot_token, default_enabled_guilds=(341001473661992962,))


# NOTE: send_webhook has to always be in discord_reminder_bot.main
def send_webhook(
    url: str = webhook_url,
    message: str = "discord-reminder-bot: Empty message.",
) -> None:
    """Send a webhook to Discord.

    Args:
        url: Our webhook url, defaults to the one from settings.
        message: The message that will be sent to Discord.
    """
    # TODO(TheLovinator): Send error to webhook  # noqa: TD003
    if not url:
        msg = "Tried to send a webhook but you have no webhook url configured."
        logger.error(msg)
        webhook: DiscordWebhook = DiscordWebhook(url=webhook_url, content=msg, rate_limit_retry=True)
        webhook.execute()
        return

    webhook: DiscordWebhook = DiscordWebhook(url=url, content=message, rate_limit_retry=True)
    response: Response = webhook.execute()
    logger.debug(response)

    if not response.ok:
        logger.critical(f"Failed to send webhook: {response.text}")


if __name__ == "__main__":
    logger.info("Starting discord-reminder-bot")
    bot.command(cmd_add.remind)
    bot.command(cmd_add.command_add)
    if os.name != "nt":
        # uvloop is 2-4x faster than default but only works on UNIX
        import uvloop  # type: ignore[import]

        logger.info("Using uvloop event loop")
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    logger.debug(f"We have {len(bot.slash_commands)} commands.")
    bot.run(asyncio_debug=True)
