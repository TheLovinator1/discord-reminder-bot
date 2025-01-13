from __future__ import annotations

import logging

import discord

logger: logging.Logger = logging.getLogger(__name__)


async def send_error_response(interaction: discord.Interaction, msg: str, *, ephemeral: bool = False) -> None:
    """Handle the error.

    Args:
        interaction (discord.Interaction): The interaction object for the command.
        msg (str): The message to send.
        ephemeral (bool, optional): Whether the message should be ephemeral. Defaults to False.
    """
    logger.exception(msg)
    await interaction.response.send_message(msg, ephemeral=ephemeral)


async def followup_msg(
    interaction: discord.Interaction,
    *,  # So that the following arguments are keyword-only
    msg: str | None = None,
    ephemeral: bool = False,
    embed: discord.Embed | None = None,
    view: discord.ui.View | None = None,
) -> None:
    """Send a followup message to the interaction.

    Handles the exceptions that may occur when sending a followup message.

    Args:
        interaction (discord.Interaction): The interaction object for the command.
        msg (str): The message to send.
        ephemeral (bool, optional): Whether the message should be ephemeral. Defaults to False.
        embed (discord.Embed | None, optional): The embed to send. Defaults to no embed.
        view (discord.ui.View | None, optional): The view to send. Defaults to no view.
    """
    if not msg:
        msg = "No message was provided."
    try:
        if embed and view:
            log_msg: str = f"Sending followup message with embed and view to the interaction.\n{msg=}.\n{ephemeral=}\n{embed.to_dict()=}"  # noqa: E501
            for view_item in view.children:
                log_msg += f"\n{view_item=}"

            logger.info(log_msg)
            await interaction.followup.send(embed=embed, ephemeral=ephemeral, view=view)
        else:
            logger.info("Sending followup message to the interaction.\nMessage: %s.\nEphemeral: %s", msg, ephemeral)
            await interaction.followup.send(content=msg, ephemeral=ephemeral)

    except (discord.NotFound, discord.Forbidden, discord.HTTPException, TypeError, ValueError) as e:
        error_messages: dict[type[discord.HTTPException | TypeError | ValueError], str] = {
            discord.NotFound: "The original message was not found.",
            discord.Forbidden: "The authorization token for the webhook is incorrect.",
            discord.HTTPException: "Failed to send followup message.",
            TypeError: "We specified both embed and embeds or file and files, or thread and threads.",
            ValueError: (
                "The length of embeds was invalid, there was no token associated with this webhook or "
                "ephemeral was passed with the improper webhook type or there was no state attached with "
                "this webhook when giving it a view."
            ),
        }
        assert_msg: str = error_messages[type(e)]
        await send_error_response(interaction=interaction, msg=assert_msg, ephemeral=ephemeral)
