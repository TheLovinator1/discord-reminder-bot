from __future__ import annotations

import lightbulb
from loguru import logger

from discord_reminder_bot.main import bot


@bot.listen(lightbulb.CommandErrorEvent)
async def on_error(event: lightbulb.CommandErrorEvent) -> None:
    """Logs command errors.

    Args:
        event: The command error event
    """
    if isinstance(event.exception, lightbulb.CommandInvocationError):
        command: lightbulb.Command | None = event.context.command
        if command is None:
            logger.error("Command invocation error occurred with no command")
            await event.context.respond("An error occurred during command invocation.")
            raise event.exception

        await event.context.respond(
            f"Something went wrong during invocation of command `{command.name}`.",
        )
        raise event.exception

    # Unwrap the exception to get the original cause
    exception: BaseException | lightbulb.LightbulbError = (
        event.exception.__cause__ or event.exception
    )

    # TODO(TheLovinator): Send error to webhook  # noqa: TD003
    logger.error(f"An error occurred during command invocation: {exception}")
    await event.context.respond(
        f"An error occurred during command invocation: {exception}",
    )
    raise exception
