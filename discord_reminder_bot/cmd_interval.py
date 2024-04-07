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
    name="weeks",
    description="Number of weeks to wait",
    required=False,
    type=hikari.OptionType.INTEGER,
)
@lightbulb.option(
    name="days",
    description="Number of days to wait",
    required=False,
    type=hikari.OptionType.INTEGER,
)
@lightbulb.option(
    name="hours",
    description="Number of hours to wait",
    required=False,
    type=hikari.OptionType.INTEGER,
)
@lightbulb.option(
    name="minutes",
    description="Number of minutes to wait",
    required=False,
    type=hikari.OptionType.INTEGER,
)
@lightbulb.option(
    name="seconds",
    description="Number of seconds to wait",
    required=False,
    type=hikari.OptionType.INTEGER,
)
@lightbulb.option(
    name="start_date",
    description="Start date of the cron job. Will get parsed by dateparser.",
    required=False,
    type=hikari.OptionType.STRING,
)
@lightbulb.option(
    name="end_date",
    description="End date of the cron job. Will get parsed by dateparser.",
    required=False,
    type=hikari.OptionType.STRING,
)
@lightbulb.option(
    name="timezone",
    description="Time zone for date/time calculations (default: scheduler timezone).",
    required=False,
    type=hikari.OptionType.STRING,
)
@lightbulb.option(
    name="jitter",
    description="Delay the job execution by x seconds at most. Adds a random component to the execution time.",
    required=False,
    type=hikari.OptionType.STRING,
)
@lightbulb.option(
    name="channel",
    description="The channel to send the message to. Defaults to the current channel.",
    required=False,
    type=hikari.OptionType.CHANNEL,
)
@lightbulb.option(name="dm_user", description="Send a message to a user.", required=False, type=hikari.OptionType.USER)
@lightbulb.command(
    name="interval",
    description="Schedules messages to be run periodically, on selected intervals.",
)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def command_interval(ctx: lightbulb.SlashContext) -> None:
    """Create a new reminder that triggers based on an interval."""
    # TODO(TheLovinator): Add reminder to database  # noqa: TD003
    # TODO(TheLovinator): Create a new type that has the options  # noqa: TD003
    # TODO(TheLovinator): Don't allow this to trigger faster than every minute  # noqa: TD003
    await ctx.respond(
        f"{ctx.options.reason=}\n{ctx.options.weeks=}\n{ctx.options.days=}\n{ctx.options.hours=}\n{ctx.options.minutes=}\n{ctx.options.seconds=}\n{ctx.options.start_date=}\n{ctx.options.end_date=}\n{ctx.options.timezone=}\n{ctx.options.jitter=}\n{ctx.options.channel=}\n{ctx.options.dm_user=}",
    )
