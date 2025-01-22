from __future__ import annotations

from discord_reminder_bot import main


def test_if_send_to_discord_is_in_main() -> None:
    """send_to_discords needs to be in main for this program to work."""
    assert hasattr(main, "send_to_discord")


def test_if_send_to_user_is_in_main() -> None:
    """send_to_user needs to be in main for this program to work."""
    assert hasattr(main, "send_to_user")
