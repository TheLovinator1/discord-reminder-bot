from typing import TYPE_CHECKING, Literal

import interactions
from apscheduler.triggers.date import DateTrigger
from interactions import ActionRow, Button, CommandContext, ComponentContext, Embed, Message, Modal, TextInput
from interactions.ext.paginator import Page, Paginator, RowPosition

from discord_reminder_bot.countdown import calculate
from discord_reminder_bot.settings import scheduler

if TYPE_CHECKING:
    from datetime import datetime

    from apscheduler.job import Job

max_message_length: Literal[1010] = 1010
max_title_length: Literal[90] = 90


async def create_pages(ctx: CommandContext) -> list[Page]:
    """Create pages for the paginator.

    Args:
        ctx: The context of the command.

    Returns:
        list[Page]: A list of pages.
    """
    pages: list[Page] = []

    jobs: list[Job] = scheduler.get_jobs()
    for job in jobs:
        channel_id: int = job.kwargs.get("channel_id")
        guild_id: int = job.kwargs.get("guild_id")

        if ctx.guild is None:
            await ctx.send("I can't find the server you're in. Are you sure you're in a server?", ephemeral=True)
            return pages
        if ctx.guild.channels is None:
            await ctx.send("I can't find the channel you're in.", ephemeral=True)
            return pages

        # Only add reminders from channels in the server we run "/reminder list" in
        # Check if channel is in the Discord server, if not, skip it.
        for channel in ctx.guild.channels:
            if int(channel.id) == channel_id or ctx.guild_id == guild_id:
                trigger_time: datetime | None = (
                    job.trigger.run_date if type(job.trigger) is DateTrigger else job.next_run_time
                )

                # Paused reminders returns None
                if trigger_time is None:
                    trigger_value: str | None = None
                    trigger_text: str = "Paused"
                else:
                    trigger_value = f'{trigger_time.strftime("%Y-%m-%d %H:%M")} (in {calculate(job)})'
                    trigger_text = trigger_value

                message: str = job.kwargs.get("message")
                message = f"{message[:1000]}..." if len(message) > max_message_length else message

                edit_button: Button = interactions.Button(
                    label="Edit",
                    style=interactions.ButtonStyle.PRIMARY,
                    custom_id="edit",
                )
                pause_button: Button = interactions.Button(
                    label="Pause",
                    style=interactions.ButtonStyle.PRIMARY,
                    custom_id="pause",
                )
                unpause_button: Button = interactions.Button(
                    label="Unpause",
                    style=interactions.ButtonStyle.PRIMARY,
                    custom_id="unpause",
                )
                remove_button: Button = interactions.Button(
                    label="Remove",
                    style=interactions.ButtonStyle.DANGER,
                    custom_id="remove",
                )

                embed: Embed = interactions.Embed(
                    title=f"{job.id}",
                    fields=[
                        interactions.EmbedField(
                            name="**Channel:**",
                            value=f"#{channel.name}",
                        ),
                        interactions.EmbedField(
                            name="**Message:**",
                            value=f"{message}",
                        ),
                    ],
                )

                if trigger_value is not None:
                    embed.add_field(
                        name="**Trigger:**",
                        value=f"{trigger_text}",
                    )
                else:
                    embed.add_field(
                        name="**Trigger:**",
                        value="_Paused_",
                    )

                components: list[Button] = [
                    edit_button,
                    remove_button,
                ]

                if type(job.trigger) is not DateTrigger:
                    # Get trigger time for cron and interval jobs
                    trigger_time = job.next_run_time
                    pause_or_unpause_button: Button = unpause_button if trigger_time is None else pause_button
                    components.insert(1, pause_or_unpause_button)

                # Add a page to pages list
                title: str = f"{message[:87]}..." if len(message) > max_title_length else message
                pages.append(
                    Page(
                        embeds=embed,
                        title=title,
                        components=ActionRow(components=components),  # type: ignore  # noqa: PGH003
                        callback=callback,
                        position=RowPosition.BOTTOM,
                    ),
                )

    return pages


async def callback(self: Paginator, ctx: ComponentContext) -> Message | None:  # noqa: PLR0911
    """Callback for the paginator."""
    if self.component_ctx is None:
        return await ctx.send("Something went wrong.", ephemeral=True)

    if self.component_ctx.message is None:
        return await ctx.send("Something went wrong.", ephemeral=True)

    job_id: str | None = self.component_ctx.message.embeds[0].title
    job: Job | None = scheduler.get_job(job_id)

    if job is None:
        return await ctx.send("Job not found.", ephemeral=True)

    channel_id: int = job.kwargs.get("channel_id")
    old_message: str = job.kwargs.get("message")

    components: list[TextInput] = [
        interactions.TextInput(
            style=interactions.TextStyleType.PARAGRAPH,
            label="New message",
            custom_id="new_message",
            value=old_message,
            required=False,
        ),
    ]

    if type(job.trigger) is DateTrigger:
        # Get trigger time for normal reminders
        trigger_time: datetime | None = job.trigger.run_date
        job_type: str = "normal"
        components.append(
            interactions.TextInput(
                style=interactions.TextStyleType.SHORT,
                label="New date, Can be human readable or ISO8601",
                custom_id="new_date",
                value=str(trigger_time),
                required=False,
            ),
        )

    else:
        # Get trigger time for cron and interval jobs
        trigger_time = job.next_run_time
        job_type = "cron/interval"

    if ctx.custom_id == "edit":
        modal: Modal = interactions.Modal(
            title=f"Edit {job_type} reminder.",
            custom_id="edit_modal",
            components=components,  # type: ignore  # noqa: PGH003
        )
        await ctx.popup(modal)
        return None

    if ctx.custom_id == "pause":
        scheduler.pause_job(job_id)
        await ctx.send(f"Job {job_id} paused.")
        return None

    if ctx.custom_id == "unpause":
        scheduler.resume_job(job_id)
        await ctx.send(f"Job {job_id} unpaused.")
        return None

    if ctx.custom_id == "remove":
        scheduler.remove_job(job_id)
        await ctx.send(
            f"Job {job_id} removed.\n"
            f"**Message:** {old_message}\n"
            f"**Channel:** {channel_id}\n"
            f"**Time:** {trigger_time}",
        )
        return None
    return None
