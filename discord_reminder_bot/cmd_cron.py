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
    name="year",
    description="4-digit year. (Example: 2042)",
    required=False,
    type=hikari.OptionType.STRING,
)
@lightbulb.option(
    name="month",
    description="Month of the year. (1-12)",
    required=False,
    type=hikari.OptionType.STRING,
)
@lightbulb.option(
    name="day",
    description="Day of the month. (1-31)",
    required=False,
    type=hikari.OptionType.STRING,
)
@lightbulb.option(
    name="week",
    description="ISO week (1-53)",
    required=False,
    type=hikari.OptionType.STRING,
)
@lightbulb.option(
    name="day_of_week",
    description="Number or name of weekday (0-6 or mon/tue/wed/thu/fri/sat/sun).",
    required=False,
    type=hikari.OptionType.STRING,
)
@lightbulb.option(
    name="hour",
    description="Hour of the day. (0-23)",
    required=False,
    type=hikari.OptionType.STRING,
)
@lightbulb.option(
    name="minute",
    description="Minute of the hour. (0-59)",
    required=False,
    type=hikari.OptionType.STRING,
)
@lightbulb.option(
    name="second",
    description="Second of the minute. (0-59)",
    required=False,
    type=hikari.OptionType.STRING,
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
    name="cron",
    description="Triggers when current time matches all specified time constraints, similarly to the UNIX cron.",
)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def command_cron(ctx: lightbulb.SlashContext) -> None:
    """Triggers when current time matches all specified time constraints, similarly to the UNIX cron."""
    # TODO(TheLovinator): Add reminder to database  # noqa: TD003
    # TODO(TheLovinator): Create a new type that has the options  # noqa: TD003
    # TODO(TheLovinator): Don't allow this to trigger faster than every minute  # noqa: TD003
    await ctx.respond(
        f"{ctx.options.reason=}\n{ctx.options.year=}\n{ctx.options.month=}\n{ctx.options.day=}\n{ctx.options.week=}\n{ctx.options.day_of_week=}\n{ctx.options.hour=}\n{ctx.options.minute=}\n{ctx.options.second=}\n{ctx.options.start_date=}\n{ctx.options.end_date=}\n{ctx.options.timezone=}\n{ctx.options.jitter=}\n{ctx.options.channel=}\n{ctx.options.dm_user=}",
    )
