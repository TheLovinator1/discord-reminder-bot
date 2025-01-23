from __future__ import annotations

from discord_reminder_bot import main


def test_if_send_to_discord_is_in_main() -> None:
    """send_to_discords needs to be in main for this program to work."""
    assert_msg: str = f"send_to_discord is not in main. Current functions in main: {dir(main)}"
    assert hasattr(main, "send_to_discord"), assert_msg


def test_if_send_to_user_is_in_main() -> None:
    """send_to_user needs to be in main for this program to work."""
    assert_msg: str = f"send_to_user is not in main. Current functions in main: {dir(main)}"
    assert hasattr(main, "send_to_user"), assert_msg
