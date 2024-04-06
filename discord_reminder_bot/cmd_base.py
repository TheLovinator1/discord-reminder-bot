"""This is the base command that will be used for all commands.

We want:
    /remind add <reason> <date_or_time> <channel> <dm_user>

Instead of:
    /add <reason> <date_or_time> <channel> <dm_user>
"""

import lightbulb


@lightbulb.command(name="remind", description="test group")
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def remind(ctx: lightbulb.SlashContext) -> None:
    """Base command for the remind group. Does nothing."""
