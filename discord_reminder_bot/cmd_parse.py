from __future__ import annotations

import lightbulb
from loguru import logger

from discord_reminder_bot.cmd_base import remind
from discord_reminder_bot.parser import ParsedTime, parse_time


@remind.child
@lightbulb.option(
    name="time_to_parse",
    description="The date or time to parse.",
    required=True,
)
@lightbulb.option(
    name="timezone",
    description="For example: 'Europe/Stockholm'.",
    required=False,
)
@lightbulb.command(name="parse", description="Find the date and time from a string.")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def command_parse(ctx: lightbulb.SlashContext) -> None:
    """Find the date and time from a string."""
    logger.debug(f"Timezone: {ctx.options.timezone}")
    logger.debug(f"Time to parse: {ctx.options.time_to_parse}")

    parsed: None | ParsedTime = parse_time(
        date_to_parse=ctx.options.time_to_parse,
        timezone=ctx.options.timezone,
    )

    if parsed is None:
        msg = f"Error: Could not parse `{ctx.options.time_to_parse}`."
        logger.error(msg)
        await ctx.respond(msg)
        return

    if parsed.error:
        msg: str = f"Error: `{parsed.error}` when parsing `{parsed.original}`."
        logger.error(msg)
        await ctx.respond(msg)
        return

    posix_timestamp: int = int(parsed.parsed.timestamp() if parsed.parsed else 0)
    msg: str = (
        f"<t:{posix_timestamp}:F>\n\n"
        f"**Original**: `{parsed.original}`\n"
        f"**Parsed**: `{parsed.parsed}`\n"
        f"**Timezone**: `{parsed.timezone}`"
    )
    logger.debug(msg)
    await ctx.respond(msg)
    return
