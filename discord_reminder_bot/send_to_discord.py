from loguru import logger


def send_msg(message: str) -> None:
    """Send a message to Discord.

    Args:
        message: The message that will be sent to Discord.
    """
    logger.debug(f"Sending message to Discord: {message}")
