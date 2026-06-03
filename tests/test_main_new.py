from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from typing import Any

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

if TYPE_CHECKING:
    from apscheduler.job import Job


def dummy_job(**kwargs: object) -> None:
    """Dummy job function for testing."""


def _make_job(
    scheduler: BackgroundScheduler,
    job_id: str,
    channel_id: int,
    author_id: int | None = None,
    message: str = "test message",
) -> Job:
    """Helper to create a job with channel kwargs for testing.

    Returns:
        The newly created APScheduler Job instance.
    """
    kwargs: dict = {
        "channel_id": channel_id,
        "message": message,
    }
    if author_id is not None:
        kwargs["author_id"] = author_id

    run_date = "2270-01-01 12:00:00"
    return scheduler.add_job(
        dummy_job,
        trigger=DateTrigger(run_date=run_date),
        id=job_id,
        name=job_id,
        kwargs=kwargs,
    )


class TestRemoveJobsByChannel:
    """Tests for the _remove_jobs_by_channel function."""

    def test_removes_matching_jobs(self) -> None:
        """Jobs targeting the given channel should be removed."""
        scheduler = BackgroundScheduler()
        scheduler.start()

        _make_job(scheduler, "job_a", channel_id=111, author_id=1)
        _make_job(scheduler, "job_b", channel_id=222, author_id=2)
        _make_job(scheduler, "job_c", channel_id=111, author_id=3)

        with patch("discord_reminder_bot.main.scheduler", scheduler), patch("discord_reminder_bot.main.send_webhook") as _:
            from discord_reminder_bot.main import _remove_jobs_by_channel

            _remove_jobs_by_channel(111)

        remaining = scheduler.get_jobs()
        remaining_ids = {j.id for j in remaining}
        assert remaining_ids == {"job_b"}, f"Expected only job_b, got {remaining_ids}"

        scheduler.shutdown()

    def test_sends_webhook_with_details(self) -> None:
        """A webhook should be sent listing removed jobs and their authors."""
        scheduler = BackgroundScheduler()
        scheduler.start()

        _make_job(scheduler, "j1", channel_id=111, author_id=42, message="water plants")
        _make_job(scheduler, "j2", channel_id=111, author_id=99, message="feed cat")

        with patch("discord_reminder_bot.main.scheduler", scheduler), patch("discord_reminder_bot.main.send_webhook") as mock_webhook:
            from discord_reminder_bot.main import _remove_jobs_by_channel

            _remove_jobs_by_channel(111)

        mock_webhook.assert_called_once()
        call_msg: str = mock_webhook.call_args[1]["message"]
        assert "j1" in call_msg
        assert "j2" in call_msg
        assert "<@42>" in call_msg
        assert "<@99>" in call_msg
        assert "water plants" in call_msg
        assert "feed cat" in call_msg

        scheduler.shutdown()

    def test_no_webhook_if_no_jobs_match(self) -> None:
        """No webhook should be sent when no jobs target the channel."""
        scheduler = BackgroundScheduler()
        scheduler.start()

        _make_job(scheduler, "j1", channel_id=999, author_id=1)

        with patch("discord_reminder_bot.main.scheduler", scheduler), patch("discord_reminder_bot.main.send_webhook") as mock_webhook:
            from discord_reminder_bot.main import _remove_jobs_by_channel

            _remove_jobs_by_channel(111)

        mock_webhook.assert_not_called()
        scheduler.shutdown()

    def test_job_already_removed(self) -> None:
        """Removing a job that was already removed should not raise."""
        scheduler = BackgroundScheduler()
        scheduler.start()

        _make_job(scheduler, "j1", channel_id=111, author_id=1)
        scheduler.remove_job("j1")

        with patch("discord_reminder_bot.main.scheduler", scheduler), patch("discord_reminder_bot.main.send_webhook") as mock_webhook:
            from discord_reminder_bot.main import _remove_jobs_by_channel

            _remove_jobs_by_channel(111)

        mock_webhook.assert_not_called()
        scheduler.shutdown()

    def test_truncates_long_messages(self) -> None:
        """Message preview in webhook should be truncated to 80 chars."""
        scheduler = BackgroundScheduler()
        scheduler.start()

        long_msg = "A" * 200
        _make_job(scheduler, "j1", channel_id=111, author_id=1, message=long_msg)

        with patch("discord_reminder_bot.main.scheduler", scheduler), patch("discord_reminder_bot.main.send_webhook") as mock_webhook:
            from discord_reminder_bot.main import _remove_jobs_by_channel

            _remove_jobs_by_channel(111)

        call_msg: str = mock_webhook.call_args[1]["message"]
        assert "A" * 80 in call_msg
        assert "A" * 81 not in call_msg
        scheduler.shutdown()

    def test_job_without_author_id(self) -> None:
        """Jobs without author_id should still be removed and listed."""
        scheduler = BackgroundScheduler()
        scheduler.start()

        _make_job(scheduler, "j1", channel_id=111, author_id=None)

        with patch("discord_reminder_bot.main.scheduler", scheduler), patch("discord_reminder_bot.main.send_webhook") as mock_webhook:
            from discord_reminder_bot.main import _remove_jobs_by_channel

            _remove_jobs_by_channel(111)

        mock_webhook.assert_called_once()
        # Should not reference <@None>
        assert "<@None>" not in mock_webhook.call_args[1]["message"]
        scheduler.shutdown()

    def test_jobs_with_different_channel_unchanged(self) -> None:
        """Jobs targeting other channels should be left untouched."""
        scheduler = BackgroundScheduler()
        scheduler.start()

        _make_job(scheduler, "keep", channel_id=222, author_id=1)
        _make_job(scheduler, "remove", channel_id=111, author_id=2)

        with patch("discord_reminder_bot.main.scheduler", scheduler), patch("discord_reminder_bot.main.send_webhook") as _:
            from discord_reminder_bot.main import _remove_jobs_by_channel

            _remove_jobs_by_channel(111)

        assert scheduler.get_job("keep") is not None
        assert scheduler.get_job("remove") is None
        scheduler.shutdown()


class TestBeforeSendSentry:
    """Tests for the Sentry before_send callback that redacts sensitive data."""

    @pytest.fixture
    def _capture_before_send(self) -> Iterator[Callable[..., Any]]:
        """Patch sentry_sdk.init and return the before_send callback.

        Avoids constructing a real RemindBotClient by directly invoking
        the logic that _init_sentry registers.

        Yields:
            The before_send callback registered with sentry_sdk.init.
        """
        with patch("discord_reminder_bot.main.sentry_sdk.init") as mock_init:
            from discord_reminder_bot.main import RemindBotClient

            # Use a mock to avoid constructing a real RemindBotClient.
            # We pass an empty lambda as _init_sentry so sentry_sdk.init is called
            # with the before_send callback. The sentry_sdk.init patch captures it.
            mock_client = MagicMock(spec=RemindBotClient)
            # _init_sentry is unbound, so we call it with mock_client as self
            RemindBotClient._init_sentry(mock_client)

            yield mock_init.call_args[1]["before_send"]

    def test_sensitive_fields_redacted_in_extra(self, _capture_before_send: Callable[..., Any]) -> None:  # noqa: PT019
        """Sensitive fields in event extra should be replaced with [redacted]."""
        before_send = _capture_before_send

        event: dict = {
            "extra": {
                "message": "secret reminder",
                "channel_id": 111,
                "author_id": 222,
                "user_id": 333,
                "guild_id": 444,
                "safe_key": "keep me",
            },
            "threads": {
                "values": [
                    {
                        "vars": {
                            "message": "leaked",
                            "channel_id": 555,
                            "safe_var": "ok",
                        },
                    },
                ],
            },
        }

        result = before_send(event, MagicMock())

        # Extra fields should be redacted
        assert result is not None
        assert result["extra"]["message"] == "[redacted]"
        assert result["extra"]["channel_id"] == "[redacted]"
        assert result["extra"]["author_id"] == "[redacted]"
        assert result["extra"]["user_id"] == "[redacted]"
        assert result["extra"]["guild_id"] == "[redacted]"
        assert result["extra"]["safe_key"] == "keep me"

        # Thread vars should be redacted
        thread_vars = result["threads"]["values"][0]["vars"]
        assert thread_vars["message"] == "[redacted]"
        assert thread_vars["channel_id"] == "[redacted]"
        assert thread_vars["safe_var"] == "ok"

    def test_nonsensitive_fields_preserved(self, _capture_before_send: Callable[..., Any]) -> None:  # noqa: PT019
        """Non-sensitive fields should be left unchanged."""
        before_send = _capture_before_send

        event: dict = {
            "extra": {
                "job_id": "abc-123",
                "scheduled_run_time": "2026-05-08T12:59:08",
                "event_code": 8192,
                "bot_is_ready": True,
            },
        }

        result = before_send(event, MagicMock())
        assert result is not None
        assert result["extra"]["job_id"] == "abc-123"
        assert result["extra"]["scheduled_run_time"] == "2026-05-08T12:59:08"
        assert result["extra"]["event_code"] == 8192
        assert result["extra"]["bot_is_ready"] is True

    def test_before_send_returns_event(self, _capture_before_send: Callable[..., Any]) -> None:  # noqa: PT019
        """before_send should always return the event (not None)."""
        before_send = _capture_before_send

        result = before_send({"extra": {}}, MagicMock())
        assert result is not None

    def test_threads_is_none(self, _capture_before_send: Callable[..., Any]) -> None:  # noqa: PT019
        """When threads is None, the function should not raise."""
        before_send = _capture_before_send

        event: dict = {"extra": {"safe": "ok"}, "threads": None}
        result = before_send(event, MagicMock())
        assert result is not None
        assert result["extra"]["safe"] == "ok"

    def test_threads_values_is_none(self, _capture_before_send: Callable[..., Any]) -> None:  # noqa: PT019
        """When threads.values is None, the function should not raise."""
        before_send = _capture_before_send

        event: dict = {"extra": {}, "threads": {"values": None}}
        result = before_send(event, MagicMock())
        assert result is not None

    def test_threads_values_is_not_list(self, _capture_before_send: Callable[..., Any]) -> None:  # noqa: PT019
        """When threads.values is not a list, the function should not raise."""
        before_send = _capture_before_send

        event: dict = {"extra": {}, "threads": {"values": "not a list"}}
        result = before_send(event, MagicMock())
        assert result is not None

    def test_threads_values_contains_non_dict(self, _capture_before_send: Callable[..., Any]) -> None:  # noqa: PT019
        """Non-dict entries in the values list should be skipped without error."""
        before_send = _capture_before_send

        event: dict = {
            "extra": {},
            "threads": {
                "values": [
                    None,
                    "string",
                    42,
                    {
                        "vars": {
                            "message": "secret",
                        },
                    },
                ],
            },
        }
        result = before_send(event, MagicMock())
        assert result is not None
        assert result["threads"]["values"][3]["vars"]["message"] == "[redacted]"

    def test_frame_without_vars(self, _capture_before_send: Callable[..., Any]) -> None:  # noqa: PT019
        """A frame dict without 'vars' should be skipped."""
        before_send = _capture_before_send

        event: dict = {
            "extra": {},
            "threads": {
                "values": [
                    {"id": 1234, "name": "MainThread"},
                ],
            },
        }
        result = before_send(event, MagicMock())
        assert result is not None

    def test_frame_vars_is_not_dict(self, _capture_before_send: Callable[..., Any]) -> None:  # noqa: PT019
        """When a frame's 'vars' is not a dict, it should be skipped."""
        before_send = _capture_before_send

        event: dict = {
            "extra": {},
            "threads": {
                "values": [
                    {"vars": "not a dict"},
                ],
            },
        }
        result = before_send(event, MagicMock())
        assert result is not None

    def test_multiple_threads_multiple_frames(self, _capture_before_send: Callable[..., Any]) -> None:  # noqa: PT019
        """Multiple threads with multiple frames should all be redacted."""
        before_send = _capture_before_send

        event: dict = {
            "extra": {},
            "threads": {
                "values": [
                    {
                        "vars": {
                            "message": "secret1",
                            "safe_val": "keep1",
                        },
                    },
                    {
                        "vars": {
                            "channel_id": 777,
                            "safe_val": "keep2",
                        },
                    },
                ],
            },
        }
        result = before_send(event, MagicMock())
        assert result is not None
        frames = result["threads"]["values"]
        assert frames[0]["vars"]["message"] == "[redacted]"
        assert frames[0]["vars"]["safe_val"] == "keep1"
        assert frames[1]["vars"]["channel_id"] == "[redacted]"
        assert frames[1]["vars"]["safe_val"] == "keep2"

    def test_empty_threads_values(self, _capture_before_send: Callable[..., Any]) -> None:  # noqa: PT019
        """An empty list of values should be handled gracefully."""
        before_send = _capture_before_send

        event: dict = {"extra": {}, "threads": {"values": []}}
        result = before_send(event, MagicMock())
        assert result is not None
        assert result["threads"]["values"] == []

    def test_threads_with_extra_keys(self, _capture_before_send: Callable[..., Any]) -> None:  # noqa: PT019
        """Threads dict may contain extra keys beyond 'values'."""
        before_send = _capture_before_send

        event: dict = {
            "extra": {},
            "threads": {
                "values": [
                    {
                        "id": 1234,
                        "name": "MainThread",
                        "vars": {
                            "message": "leaked",
                            "author_id": 999,
                        },
                    },
                ],
            },
        }
        result = before_send(event, MagicMock())
        assert result is not None
        frame_vars = result["threads"]["values"][0]["vars"]
        assert frame_vars["message"] == "[redacted]"
        assert frame_vars["author_id"] == "[redacted]"


class TestSendToDiscordChannelNotFound:
    """Tests for send_to_discord when the channel is deleted or inaccessible."""

    @pytest.mark.asyncio
    async def test_discord_not_found_removes_jobs(self) -> None:
        """discord.NotFound should call _remove_jobs_by_channel and return."""
        with (
            patch("discord_reminder_bot.main.bot") as mock_bot,
            patch("discord_reminder_bot.main._remove_jobs_by_channel") as mock_remove,
            patch("discord_reminder_bot.main.logger"),
        ):
            mock_bot.is_ready.return_value = True
            mock_bot.is_closed.return_value = False
            mock_bot.get_channel.return_value = None
            mock_bot.fetch_channel.side_effect = __import__("discord").NotFound(MagicMock(), MagicMock())

            from discord_reminder_bot.main import send_to_discord

            await send_to_discord(channel_id=111, message="test", author_id=1)

            mock_remove.assert_called_once_with(111)

    @pytest.mark.asyncio
    async def test_discord_forbidden_fetch_returns_gracefully(self) -> None:
        """discord.Forbidden when fetching should log and return, not remove jobs."""
        with (
            patch("discord_reminder_bot.main.bot") as mock_bot,
            patch("discord_reminder_bot.main._remove_jobs_by_channel") as mock_remove,
            patch("discord_reminder_bot.main.logger"),
        ):
            mock_bot.is_ready.return_value = True
            mock_bot.is_closed.return_value = False
            mock_bot.get_channel.return_value = None
            mock_bot.fetch_channel.side_effect = __import__("discord").Forbidden(MagicMock(), MagicMock())

            from discord_reminder_bot.main import send_to_discord

            await send_to_discord(channel_id=111, message="test", author_id=1)

            mock_remove.assert_not_called()

    @pytest.mark.asyncio
    async def test_discord_forbidden_send_returns_gracefully(self) -> None:
        """discord.Forbidden when sending should log and return, not raise."""
        with (
            patch("discord_reminder_bot.main.bot") as mock_bot,
            patch("discord_reminder_bot.main._remove_jobs_by_channel") as mock_remove,
            patch("discord_reminder_bot.main.logger"),
        ):
            mock_bot.is_ready.return_value = True
            mock_bot.is_closed.return_value = False

            mock_channel = MagicMock()
            mock_channel.send.side_effect = __import__("discord").Forbidden(MagicMock(), MagicMock())
            mock_bot.get_channel.return_value = mock_channel

            from discord_reminder_bot.main import send_to_discord

            await send_to_discord(channel_id=111, message="test", author_id=1)

            mock_remove.assert_not_called()


class TestRemindListThreadSupport:
    """Tests for the changes in commit adcdba9: allow threads in /remind list."""

    def test_isinstance_check_includes_thread(self) -> None:
        """The isinstance check for channel should include discord.Thread."""
        import inspect

        from discord_reminder_bot.main import RemindGroup

        # RemindGroup.list is a discord.app_commands.Command; .callback is the original function
        source = inspect.getsource(RemindGroup.list.callback)
        assert "discord.Thread" in source, f"Expected discord.Thread in source, got partial:\n{source[:300]}"

    def test_guild_channels_includes_threads(self) -> None:
        """The guild channels list should include thread IDs."""
        import inspect

        from discord_reminder_bot.main import RemindGroup

        source = inspect.getsource(RemindGroup.list.callback)
        assert "guild.threads" in source, f"Expected guild.threads in source, got partial:\n{source[:300]}"


class TestFormatJobNotification:
    """Tests for the _format_job_notification helper function."""

    def test_with_job_data(self) -> None:
        """When job_data is provided, a JSON code block should be included."""
        from discord_reminder_bot.main import _format_job_notification

        result: str = _format_job_notification(
            job_id="abc123",
            job_data='{"id": "abc123", "kwargs": {"message": "hello"}}',
            prefix="was removed because channel <#111> was deleted.",
        )
        assert "Job abc123" in result
        assert "was removed because channel" in result
        assert "```json" in result
        assert '{"id": "abc123"' in result
        assert "```" in result

    def test_without_job_data(self) -> None:
        """When job_data is empty, no code block should be present."""
        from discord_reminder_bot.main import _format_job_notification

        result: str = _format_job_notification(
            job_id="abc123",
            job_data="",
            prefix="was missed! Was scheduled at 2026-01-01 12:00:00",
        )
        assert result == "Job abc123 was missed! Was scheduled at 2026-01-01 12:00:00\n"
        assert "```" not in result

    def test_with_none_job_data(self) -> None:
        """When job_data is None (treated as falsy), no code block."""
        from discord_reminder_bot.main import _format_job_notification

        result: str = _format_job_notification(
            job_id="abc123",
            job_data="",
            prefix="was missed!",
        )
        assert "```" not in result


class TestNotifyChannelJobRemoved:
    """Tests for the _notify_channel_job_removed function."""

    @patch("discord_reminder_bot.main._find_job_data_by_channel_in_markdown")
    @patch("discord_reminder_bot.main.send_webhook")
    @patch("discord_reminder_bot.main.logger")
    def test_with_markdown_data(
        self,
        mock_logger: MagicMock,
        mock_webhook: MagicMock,
        mock_find: MagicMock,
    ) -> None:
        """When markdown data is found, it should be included in the webhook."""
        job_data: str = json.dumps({"id": "my-job-id", "kwargs": {"channel_id": 111}})
        mock_find.return_value = job_data

        from discord_reminder_bot.main import _notify_channel_job_removed

        _notify_channel_job_removed(channel_id=111, author_id=42, message="hello")

        mock_webhook.assert_called_once()
        call_msg: str = mock_webhook.call_args[1]["message"]
        assert "my-job-id" in call_msg
        assert "```json" in call_msg
        assert job_data in call_msg
        assert "<#111>" in call_msg

    @patch("discord_reminder_bot.main._find_job_data_by_channel_in_markdown")
    @patch("discord_reminder_bot.main.send_webhook")
    @patch("discord_reminder_bot.main.logger")
    def test_without_markdown_data(
        self,
        mock_logger: MagicMock,
        mock_webhook: MagicMock,
        mock_find: MagicMock,
    ) -> None:
        """When no markdown data is found, fallback info should be included."""
        mock_find.return_value = None

        from discord_reminder_bot.main import _notify_channel_job_removed

        _notify_channel_job_removed(channel_id=222, author_id=99, message="fallback test")

        mock_webhook.assert_called_once()
        call_msg: str = mock_webhook.call_args[1]["message"]
        assert "(unknown id)" in call_msg
        assert 'Message: "fallback test"' in call_msg
        assert "<@99>" in call_msg
        assert "```" not in call_msg

    @patch("discord_reminder_bot.main._find_job_data_by_channel_in_markdown")
    @patch("discord_reminder_bot.main.send_webhook")
    @patch("discord_reminder_bot.main.logger")
    def test_truncates_long_message_fallback(
        self,
        mock_logger: MagicMock,
        mock_webhook: MagicMock,
        mock_find: MagicMock,
    ) -> None:
        """The fallback message should be truncated to 80 chars."""
        mock_find.return_value = None
        long_msg: str = "X" * 200

        from discord_reminder_bot.main import _notify_channel_job_removed

        _notify_channel_job_removed(channel_id=333, author_id=1, message=long_msg)

        call_msg: str = mock_webhook.call_args[1]["message"]
        assert "X" * 80 in call_msg
        assert "X" * 81 not in call_msg

    @patch("discord_reminder_bot.main._find_job_data_by_channel_in_markdown")
    @patch("discord_reminder_bot.main.send_webhook")
    @patch("discord_reminder_bot.main.logger")
    def test_empty_message_fallback(
        self,
        mock_logger: MagicMock,
        mock_webhook: MagicMock,
        mock_find: MagicMock,
    ) -> None:
        """An empty message in fallback should show empty string."""
        mock_find.return_value = None

        from discord_reminder_bot.main import _notify_channel_job_removed

        _notify_channel_job_removed(channel_id=444, author_id=1, message="")

        call_msg: str = mock_webhook.call_args[1]["message"]
        assert 'Message: ""' in call_msg

    @patch("discord_reminder_bot.main._find_job_data_by_channel_in_markdown")
    @patch("discord_reminder_bot.main.send_webhook")
    @patch("discord_reminder_bot.main.logger")
    def test_none_message_fallback(
        self,
        mock_logger: MagicMock,
        mock_webhook: MagicMock,
        mock_find: MagicMock,
    ) -> None:
        """A None message in fallback should be handled gracefully."""
        mock_find.return_value = None

        from discord_reminder_bot.main import _notify_channel_job_removed

        _notify_channel_job_removed(channel_id=555, author_id=1, message="")

        call_msg: str = mock_webhook.call_args[1]["message"]
        assert 'Message: ""' in call_msg

    @patch("discord_reminder_bot.main._find_job_data_by_channel_in_markdown")
    @patch("discord_reminder_bot.main.send_webhook")
    @patch("discord_reminder_bot.main.logger")
    def test_markdown_data_without_id(
        self,
        mock_logger: MagicMock,
        mock_webhook: MagicMock,
        mock_find: MagicMock,
    ) -> None:
        """When markdown data lacks an 'id' field, '(unknown id)' should be used."""
        mock_find.return_value = json.dumps({"kwargs": {"channel_id": 666}})

        from discord_reminder_bot.main import _notify_channel_job_removed

        _notify_channel_job_removed(channel_id=666, author_id=1, message="test")

        call_msg: str = mock_webhook.call_args[1]["message"]
        assert "(unknown id)" in call_msg
        assert "```json" in call_msg

    @patch("discord_reminder_bot.main._find_job_data_by_channel_in_markdown")
    @patch("discord_reminder_bot.main.send_webhook")
    @patch("discord_reminder_bot.main.logger")
    def test_markdown_data_with_numeric_id(
        self,
        mock_logger: MagicMock,
        mock_webhook: MagicMock,
        mock_find: MagicMock,
    ) -> None:
        """If the 'id' field is numeric, it should still be used as a string."""
        mock_find.return_value = json.dumps({"id": 12345, "kwargs": {"channel_id": 777}})

        from discord_reminder_bot.main import _notify_channel_job_removed

        _notify_channel_job_removed(channel_id=777, author_id=1, message="test")

        call_msg: str = mock_webhook.call_args[1]["message"]
        assert "(unknown id)" in call_msg, "Numeric id should not match str check"


class TestFindJobDataByChannelInMarkdown:
    """Tests for the _find_job_data_by_channel_in_markdown function."""

    def test_returns_none_when_dir_missing(self, tmp_path: Path) -> None:
        """When the reminder_data directory does not exist, None should be returned."""
        import os

        from discord_reminder_bot.main import _find_job_data_by_channel_in_markdown

        with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}):
            result = _find_job_data_by_channel_in_markdown(111)
            assert result is None

    def test_returns_none_when_no_match(self, tmp_path: Path) -> None:
        """When no file has a matching channel_id, None should be returned."""
        import os

        reminder_dir = tmp_path / "reminder_data"
        reminder_dir.mkdir()
        job_file = reminder_dir / "other-job.md"
        job_file.write_text(json.dumps({"id": "other", "kwargs": {"channel_id": 999}}), encoding="utf-8")

        from discord_reminder_bot.main import _find_job_data_by_channel_in_markdown

        with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}):
            result = _find_job_data_by_channel_in_markdown(111)
            assert result is None

    def test_returns_matching_file_content(self, tmp_path: Path) -> None:
        """When a file matches the channel_id, its full content should be returned."""
        import os

        reminder_dir = tmp_path / "reminder_data"
        reminder_dir.mkdir()
        job_data: dict = {"id": "abc123", "kwargs": {"channel_id": 111, "message": "hello"}}
        content: str = json.dumps(job_data)
        job_file = reminder_dir / "abc123.md"
        job_file.write_text(content, encoding="utf-8")

        # Add a non-matching file
        other_file = reminder_dir / "other.md"
        other_file.write_text(json.dumps({"id": "other", "kwargs": {"channel_id": 999}}), encoding="utf-8")

        from discord_reminder_bot.main import _find_job_data_by_channel_in_markdown

        with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}):
            result = _find_job_data_by_channel_in_markdown(111)
            assert result == content

    def test_skips_non_md_files(self, tmp_path: Path) -> None:
        """Files without .md extension should be skipped."""
        import os

        reminder_dir = tmp_path / "reminder_data"
        reminder_dir.mkdir()
        txt_file = reminder_dir / "data.txt"
        txt_file.write_text(json.dumps({"id": "txt-job", "kwargs": {"channel_id": 111}}), encoding="utf-8")

        from discord_reminder_bot.main import _find_job_data_by_channel_in_markdown

        with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}):
            result = _find_job_data_by_channel_in_markdown(111)
            assert result is None

    def test_skips_invalid_json(self, tmp_path: Path) -> None:
        """Files with invalid JSON should be skipped."""
        import os

        reminder_dir = tmp_path / "reminder_data"
        reminder_dir.mkdir()
        bad_file = reminder_dir / "bad.md"
        bad_file.write_text("not valid json", encoding="utf-8")

        from discord_reminder_bot.main import _find_job_data_by_channel_in_markdown

        with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}):
            result = _find_job_data_by_channel_in_markdown(111)
            assert result is None

    def test_returns_first_match(self, tmp_path: Path) -> None:
        """When multiple files match, the first one found should be returned."""
        import os

        reminder_dir = tmp_path / "reminder_data"
        reminder_dir.mkdir()
        first: dict = {"id": "first", "kwargs": {"channel_id": 111}}
        second: dict = {"id": "second", "kwargs": {"channel_id": 111}}
        (reminder_dir / "first.md").write_text(json.dumps(first), encoding="utf-8")
        (reminder_dir / "second.md").write_text(json.dumps(second), encoding="utf-8")

        from discord_reminder_bot.main import _find_job_data_by_channel_in_markdown

        with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}):
            result = _find_job_data_by_channel_in_markdown(111)
            # Should return one of them (order depends on filesystem)
            assert result is not None


class TestSendWebhook:
    """Tests for the send_webhook function.

    Verifies that the function handles the optional ``custom_url`` parameter
    correctly, falling back to ``WEBHOOK_URL`` env var when not provided.
    """

    WEBHOOK_ENV_VAR: str = "WEBHOOK_URL"

    @patch("discord_reminder_bot.main.os.getenv")
    @patch("discord_reminder_bot.main.DiscordWebhook")
    @patch("discord_reminder_bot.main.logger")
    def test_without_custom_url_uses_env_var(
        self,
        mock_logger: MagicMock,
        mock_webhook_cls: MagicMock,
        mock_getenv: MagicMock,
    ) -> None:
        """When custom_url is not provided, the WEBHOOK_URL env var should be used."""
        mock_getenv.return_value = "https://discord.com/api/webhooks/env"
        mock_instance = MagicMock()
        mock_webhook_cls.return_value = mock_instance

        from discord_reminder_bot.main import send_webhook

        send_webhook(message="test message")

        mock_getenv.assert_called_with(self.WEBHOOK_ENV_VAR)
        mock_webhook_cls.assert_called_once_with(
            url="https://discord.com/api/webhooks/env",
            content="test message",
            rate_limit_retry=True,
        )
        mock_instance.execute.assert_called_once()

    @patch("discord_reminder_bot.main.os.getenv")
    @patch("discord_reminder_bot.main.DiscordWebhook")
    @patch("discord_reminder_bot.main.logger")
    def test_with_custom_url(
        self,
        mock_logger: MagicMock,
        mock_webhook_cls: MagicMock,
        mock_getenv: MagicMock,
    ) -> None:
        """When custom_url is provided, it should be used instead of the env var."""
        mock_instance = MagicMock()
        mock_webhook_cls.return_value = mock_instance

        from discord_reminder_bot.main import send_webhook

        send_webhook(custom_url="https://discord.com/api/webhooks/custom", message="test message")

        # getenv should still be called but the result should be ignored
        mock_webhook_cls.assert_called_once_with(
            url="https://discord.com/api/webhooks/custom",
            content="test message",
            rate_limit_retry=True,
        )
        mock_instance.execute.assert_called_once()

    @patch("discord_reminder_bot.main.os.getenv")
    @patch("discord_reminder_bot.main.DiscordWebhook")
    @patch("discord_reminder_bot.main.logger")
    def test_no_webhook_url_configured(
        self,
        mock_logger: MagicMock,
        mock_webhook_cls: MagicMock,
        mock_getenv: MagicMock,
    ) -> None:
        """When no URL is available from either source, the function should skip silently."""
        mock_getenv.return_value = None

        from discord_reminder_bot.main import send_webhook

        send_webhook(message="test message")

        mock_webhook_cls.assert_not_called()
        mock_logger.info.assert_any_call(
            "No webhook URL configured (WEBHOOK_URL env var not set). Skipping webhook.",
        )

    @patch("discord_reminder_bot.main.os.getenv")
    @patch("discord_reminder_bot.main.DiscordWebhook")
    @patch("discord_reminder_bot.main.logger")
    def test_empty_message_warning(
        self,
        mock_logger: MagicMock,
        mock_webhook_cls: MagicMock,
        mock_getenv: MagicMock,
    ) -> None:
        """When message is empty, a warning should be logged and fallback message used."""
        mock_getenv.return_value = "https://discord.com/api/webhooks/env"
        mock_instance = MagicMock()
        mock_webhook_cls.return_value = mock_instance

        from discord_reminder_bot.main import send_webhook

        send_webhook(message="")

        mock_logger.warning.assert_called_with("No message provided.")
        mock_webhook_cls.assert_called_once_with(
            url="https://discord.com/api/webhooks/env",
            content="No message provided.",
            rate_limit_retry=True,
        )

    @patch("discord_reminder_bot.main.os.getenv")
    @patch("discord_reminder_bot.main.DiscordWebhook")
    @patch("discord_reminder_bot.main.logger")
    def test_custom_url_overrides_env_var(
        self,
        mock_logger: MagicMock,
        mock_webhook_cls: MagicMock,
        mock_getenv: MagicMock,
    ) -> None:
        """custom_url should take precedence over WEBHOOK_URL env var."""
        mock_getenv.return_value = "https://discord.com/api/webhooks/env"

        mock_instance = MagicMock()
        mock_webhook_cls.return_value = mock_instance

        from discord_reminder_bot.main import send_webhook

        send_webhook(custom_url="https://discord.com/api/webhooks/custom", message="override test")

        mock_webhook_cls.assert_called_once_with(
            url="https://discord.com/api/webhooks/custom",
            content="override test",
            rate_limit_retry=True,
        )

    @patch("discord_reminder_bot.main.os.getenv")
    @patch("discord_reminder_bot.main.DiscordWebhook")
    @patch("discord_reminder_bot.main.logger")
    def test_custom_url_none_explicit(
        self,
        mock_logger: MagicMock,
        mock_webhook_cls: MagicMock,
        mock_getenv: MagicMock,
    ) -> None:
        """Passing custom_url=None explicitly should behave the same as omitting it."""
        mock_getenv.return_value = "https://discord.com/api/webhooks/env"
        mock_instance = MagicMock()
        mock_webhook_cls.return_value = mock_instance

        from discord_reminder_bot.main import send_webhook

        send_webhook(custom_url=None, message="explicit none")

        mock_getenv.assert_called_with(self.WEBHOOK_ENV_VAR)
        mock_webhook_cls.assert_called_once_with(
            url="https://discord.com/api/webhooks/env",
            content="explicit none",
            rate_limit_retry=True,
        )
