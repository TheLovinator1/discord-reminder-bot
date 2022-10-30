from discord_reminder_bot import main


def test_if_send_to_discord_is_in_main():
    """
    send_to_discords needs to be in main for this program to work.
    """
    assert hasattr(main, "send_to_discord")
