import hikari
import lightbulb

from discord_reminder_bot.cmd_base import remind


@remind.child
@lightbulb.option(
    name="reason",
    description="The message that will be sent when the reminder is triggered.",
    required=True,
    type=hikari.OptionType.STRING,
)
@lightbulb.option(
    name="date_or_time",
    description="The date to send the message. Will get parsed by dateparser.",
    required=True,
    type=hikari.OptionType.STRING,
)
@lightbulb.option(
    name="channel",
    description="The channel to send the message to. Defaults to the current channel.",
    required=False,
    type=hikari.OptionType.CHANNEL,
)
@lightbulb.option(name="dm_user", description="Send a message to a user.", required=False, type=hikari.OptionType.USER)
@lightbulb.command(name="add", description="Add a reminder.")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def command_add(ctx: lightbulb.SlashContext) -> None:
    """Add a reminder."""
    # TODO(TheLovinator): Add reminder to database  # noqa: TD003
    # TODO(TheLovinator): Create a new type that has the options  # noqa: TD003
    # TODO(TheLovinator): Add the reminder to the scheduler  # noqa: TD003
    # TODO(TheLovinator): Send a confirmation message  # noqa: TD003
    # TODO(TheLovinator): Send a webhook  # noqa: TD003
    await ctx.respond(
        f"{ctx.options.reason=}\n{ctx.options.date_or_time=}\n{ctx.options.channel=}\n{ctx.options.dm_user=}",
    )
