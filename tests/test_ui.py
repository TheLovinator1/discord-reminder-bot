from __future__ import annotations

import unittest
from unittest.mock import Mock

import discord
from apscheduler.triggers.interval import IntervalTrigger

from discord_reminder_bot.ui import create_job_embed


class TestCreateJobEmbed(unittest.TestCase):
    """Test the `create_job_embed` function in the `discord_reminder_bot.ui` module."""

    def setUp(self) -> None:
        """Set up the mock job for testing."""
        self.job = Mock()
        self.job.id = "12345"
        self.job.kwargs = {"channel_id": 67890, "message": "Test message", "author_id": 54321}
        self.job.next_run_time = None
        self.job.trigger = Mock(spec=IntervalTrigger)
        self.job.trigger.interval = "1 day"

    def test_create_job_embed_with_next_run_time(self) -> None:
        """Test the `create_job_embed` function to ensure it correctly creates a Discord embed for a job with the next run time."""
        self.job.next_run_time = Mock()
        self.job.next_run_time.strftime.return_value = "2023-10-10 10:00:00"

        embed: discord.Embed = create_job_embed(self.job)

        assert isinstance(embed, discord.Embed)
        assert embed.title == "Test message"
        assert embed.description is not None
        assert "ID: 12345" in embed.description
        assert "Next run: 2023-10-10 10:00:00" in embed.description
        assert "Interval: 1 day" in embed.description
        assert "Channel: <#67890>" in embed.description
        assert "Author: <@54321>" in embed.description

    def test_create_job_embed_without_next_run_time(self) -> None:
        """Test the `create_job_embed` function to ensure it correctly creates a Discord embed for a job without the next run time."""
        embed: discord.Embed = create_job_embed(self.job)

        assert isinstance(embed, discord.Embed)
        assert embed.title == "Test message"
        assert embed.description is not None
        assert "ID: 12345" in embed.description
        assert "Paused" in embed.description
        assert "Interval: 1 day" in embed.description
        assert "Channel: <#67890>" in embed.description
        assert "Author: <@54321>" in embed.description

    def test_create_job_embed_with_long_message(self) -> None:
        """Test the `create_job_embed` function to ensure it correctly truncates long messages."""
        self.job.kwargs["message"] = "A" * 300

        embed: discord.Embed = create_job_embed(self.job)

        assert isinstance(embed, discord.Embed)
        assert embed.title == "A" * 256 + "..."
        assert embed.description is not None
        assert "ID: 12345" in embed.description
        assert "Paused" in embed.description
        assert "Interval: 1 day" in embed.description
        assert "Channel: <#67890>" in embed.description
        assert "Author: <@54321>" in embed.description


if __name__ == "__main__":
    unittest.main()
