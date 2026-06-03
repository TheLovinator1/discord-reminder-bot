from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

if TYPE_CHECKING:
    from apscheduler.job import Job

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from discord_reminder_bot.modals import (
    CronReminderModifyModal,
    DateReminderModifyModal,
    IntervalReminderModifyModal,
)


def dummy_job(**kwargs: object) -> None:
    """Dummy job function for testing."""


def _make_date_job(
    scheduler: BackgroundScheduler,
    job_id: str = "test_job",
    message: str = "test message",
    author_id: int = 1,
    channel_id: int = 111,
) -> Job:
    """Create a date-based job for testing.

    Args:
        scheduler: The scheduler to add the job to.
        job_id: The job ID.
        message: The reminder message.
        author_id: The author's user ID.
        channel_id: The target channel ID.

    Returns:
        The newly created APScheduler Job instance.
    """
    kwargs: dict = {
        "channel_id": channel_id,
        "message": message,
        "author_id": author_id,
    }
    run_date = "2270-01-01 12:00:00"
    return scheduler.add_job(
        dummy_job,
        trigger=DateTrigger(run_date=run_date),
        id=job_id,
        name=job_id,
        kwargs=kwargs,
    )


def _mock_interaction() -> MagicMock:
    """Create a mock Discord interaction for testing.

    Returns:
        A MagicMock configured with async response methods.
    """
    interaction = MagicMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


class TestDefaultMessageTruncation:
    """Tests for the default message truncation in _BaseReminderModifyModal."""

    def test_default_message_truncated_to_200_chars(self) -> None:
        """A message longer than 200 chars should be truncated in the TextInput default."""
        scheduler = BackgroundScheduler()
        scheduler.start()

        long_msg = "A" * 210
        job = _make_date_job(scheduler, message=long_msg)

        with patch("discord_reminder_bot.modals.scheduler", scheduler):
            modal = DateReminderModifyModal(job)

        default_value: str = modal.message_input.default or ""
        assert len(default_value) == 200, f"Expected default to be truncated to 200 chars, got {len(default_value)}"
        assert default_value == "A" * 200
        assert modal._full_original_message == long_msg, "Expected _full_original_message to store the full 210-char message"

        scheduler.shutdown()

    def test_default_message_under_200_chars_unchanged(self) -> None:
        """A message under 200 chars should not be truncated."""
        scheduler = BackgroundScheduler()
        scheduler.start()

        short_msg = "short message"
        job = _make_date_job(scheduler, message=short_msg)

        with patch("discord_reminder_bot.modals.scheduler", scheduler):
            modal = DateReminderModifyModal(job)

        default_value: str = modal.message_input.default or ""
        assert default_value == short_msg
        assert modal._full_original_message == short_msg

        scheduler.shutdown()

    def test_default_message_exactly_200_chars_unchanged(self) -> None:
        """A message exactly 200 chars should not be truncated."""
        scheduler = BackgroundScheduler()
        scheduler.start()

        exact_msg = "B" * 200
        job = _make_date_job(scheduler, message=exact_msg)

        with patch("discord_reminder_bot.modals.scheduler", scheduler):
            modal = DateReminderModifyModal(job)

        default_value: str = modal.message_input.default or ""
        assert default_value == exact_msg
        assert modal._full_original_message == exact_msg

        scheduler.shutdown()

    def test_input_required_false(self) -> None:
        """The message TextInput should have required=False."""
        scheduler = BackgroundScheduler()
        scheduler.start()

        job = _make_date_job(scheduler)

        with patch("discord_reminder_bot.modals.scheduler", scheduler):
            modal = DateReminderModifyModal(job)

        assert modal.message_input.required is False

        scheduler.shutdown()

    def test_time_input_required_false(self) -> None:
        """The time TextInput in DateReminderModifyModal should have required=False."""
        scheduler = BackgroundScheduler()
        scheduler.start()

        job = _make_date_job(scheduler)

        with patch("discord_reminder_bot.modals.scheduler", scheduler):
            modal = DateReminderModifyModal(job)

        assert modal.time_input.required is False

        scheduler.shutdown()


class TestDateReminderModifyModalApplyTriggerChanges:
    """Tests for DateReminderModifyModal._apply_trigger_changes."""

    @pytest.fixture
    def scheduler_and_job(self) -> tuple[BackgroundScheduler, Job]:
        """Create a scheduler with a date job for testing.

        Returns:
            A tuple of (BackgroundScheduler, Job) with a date-based job added.
        """
        scheduler = BackgroundScheduler()
        scheduler.start()
        job = _make_date_job(scheduler, job_id="date_test", message="water plants")
        return scheduler, job

    @pytest.mark.asyncio
    async def test_empty_time_keeps_existing_time(self, scheduler_and_job: tuple[BackgroundScheduler, Job]) -> None:
        """An empty time input should return no-change (True, '')."""
        scheduler, job = scheduler_and_job
        mock_interaction = _mock_interaction()

        with patch("discord_reminder_bot.modals.scheduler", scheduler):
            modal = DateReminderModifyModal(job)
            modal.time_input._value = ""
            success, msg = modal._apply_trigger_changes(mock_interaction)

        assert success is True, f"Expected success=True, got {success}"
        assert not msg, f"Expected empty message, got {msg!r}"

        # Verify the job's run time was not changed
        assert scheduler.get_job("date_test") is not None

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_whitespace_time_keeps_existing_time(self, scheduler_and_job: tuple[BackgroundScheduler, Job]) -> None:
        """A whitespace-only time input should return no-change (True, '')."""
        scheduler, job = scheduler_and_job
        mock_interaction = _mock_interaction()

        with patch("discord_reminder_bot.modals.scheduler", scheduler):
            modal = DateReminderModifyModal(job)
            modal.time_input._value = "   "
            success, msg = modal._apply_trigger_changes(mock_interaction)

        assert success is True, f"Expected success=True, got {success}"
        assert not msg, f"Expected empty message, got {msg!r}"

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_invalid_time_returns_error(self, scheduler_and_job: tuple[BackgroundScheduler, Job]) -> None:
        """An invalid time format should return an error message."""
        scheduler, job = scheduler_and_job
        mock_interaction = _mock_interaction()

        with patch("discord_reminder_bot.modals.scheduler", scheduler):
            modal = DateReminderModifyModal(job)
            modal.time_input._value = "not a valid time at all 12345"
            success, msg = modal._apply_trigger_changes(mock_interaction)

        assert success is False, f"Expected success=False, got {success}"
        assert "Invalid time format" in msg
        assert "not a valid time at all 12345" in msg

        scheduler.shutdown()


class TestBaseModalOnSubmit:
    """Tests for _BaseReminderModifyModal.on_submit."""

    @pytest.fixture
    def scheduler_and_job(self) -> tuple[BackgroundScheduler, Job]:
        """Create a scheduler with a date job for testing.

        Returns:
            A tuple of (BackgroundScheduler, Job) with a date-based job added.
        """
        scheduler = BackgroundScheduler()
        scheduler.start()
        job = _make_date_job(scheduler, job_id="submit_test", message="feed the cat")
        return scheduler, job

    @pytest.mark.asyncio
    async def test_empty_message_keeps_original_message(self, scheduler_and_job: tuple[BackgroundScheduler, Job]) -> None:
        """An empty message input should keep the original job message unchanged."""
        scheduler, job = scheduler_and_job
        mock_interaction = _mock_interaction()

        with patch("discord_reminder_bot.modals.scheduler", scheduler):
            modal = DateReminderModifyModal(job)
            modal.message_input._value = ""
            modal.time_input._value = ""
            await modal.on_submit(mock_interaction)

        # The job's message should still be the original
        modified_job = scheduler.get_job("submit_test")
        assert modified_job is not None, "Job should still exist"
        assert modified_job.kwargs["message"] == "feed the cat", (
            f"Expected message to remain 'feed the cat', got {modified_job.kwargs['message']!r}"
        )

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_new_message_updates_job(self, scheduler_and_job: tuple[BackgroundScheduler, Job]) -> None:
        """A non-empty message input should update the job's message."""
        scheduler, job = scheduler_and_job
        mock_interaction = _mock_interaction()

        with patch("discord_reminder_bot.modals.scheduler", scheduler):
            modal = DateReminderModifyModal(job)
            modal.message_input._value = "new message text"
            modal.time_input._value = ""
            await modal.on_submit(mock_interaction)

        modified_job = scheduler.get_job("submit_test")
        assert modified_job is not None, "Job should still exist"
        assert modified_job.kwargs["message"] == "new message text", (
            f"Expected message to be 'new message text', got {modified_job.kwargs['message']!r}"
        )

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_long_message_kept_when_input_empty(self) -> None:
        """When original message is >200 chars and input is empty, the full message should be preserved."""
        scheduler = BackgroundScheduler()
        scheduler.start()

        long_msg = "A" * 210
        job = _make_date_job(scheduler, job_id="long_msg_test", message=long_msg)
        mock_interaction = _mock_interaction()

        with patch("discord_reminder_bot.modals.scheduler", scheduler):
            modal = DateReminderModifyModal(job)
            modal.message_input._value = ""
            modal.time_input._value = ""
            await modal.on_submit(mock_interaction)

        modified_job = scheduler.get_job("long_msg_test")
        assert modified_job is not None, "Job should still exist"
        assert modified_job.kwargs["message"] == long_msg, (
            f"Expected the full 210-char message to be preserved, got {len(modified_job.kwargs['message'])} chars"
        )

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_no_changes_reports_no_changes(self, scheduler_and_job: tuple[BackgroundScheduler, Job]) -> None:
        """Submitting with no changes should send a 'no changes' message."""
        scheduler, job = scheduler_and_job
        mock_interaction = _mock_interaction()

        with patch("discord_reminder_bot.modals.scheduler", scheduler):
            modal = DateReminderModifyModal(job)
            modal.message_input._value = "feed the cat"
            modal.time_input._value = ""
            await modal.on_submit(mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_kwargs = mock_interaction.followup.send.call_args[1]
        assert "No changes made" in call_kwargs.get("content", ""), f"Expected 'No changes made' in response, got {call_kwargs}"
        assert call_kwargs.get("ephemeral") is True

        scheduler.shutdown()


class TestCronAndIntervalModals:
    """Tests for CronReminderModifyModal and IntervalReminderModifyModal."""

    def test_cron_modal_message_input_required_false(self) -> None:
        """CronReminderModifyModal should have message_input with required=False."""
        scheduler = BackgroundScheduler()
        scheduler.start()

        job = _make_date_job(scheduler)
        with patch("discord_reminder_bot.modals.scheduler", scheduler):
            modal = CronReminderModifyModal(job)

        assert modal.message_input.required is False

        scheduler.shutdown()

    def test_interval_modal_message_input_required_false(self) -> None:
        """IntervalReminderModifyModal should have message_input with required=False."""
        scheduler = BackgroundScheduler()
        scheduler.start()

        job = _make_date_job(scheduler)
        with patch("discord_reminder_bot.modals.scheduler", scheduler):
            modal = IntervalReminderModifyModal(job)

        assert modal.message_input.required is False

        scheduler.shutdown()
