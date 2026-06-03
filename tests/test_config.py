"""Tests for the ``_config`` module (timezone loading)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
import pytz

from discord_reminder_bot._config import get_scheduler_timezone

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _reset_timezone_cache() -> Iterator[None]:
    """Reset the module-level timezone cache before and after each test.

    This ensures each test starts with a clean slate, unaffected by earlier
    tests or by the ``pytest_configure`` default in ``conftest.py``.
    """
    import discord_reminder_bot._config as cfg

    saved: pytz.BaseTzInfo | None = cfg.SCHEDULER_TIMEZONE
    cfg.SCHEDULER_TIMEZONE = None
    try:
        yield
    finally:
        cfg.SCHEDULER_TIMEZONE = saved


class TestGetSchedulerTimezone:
    """Tests for ``get_scheduler_timezone()``."""

    def test_returns_correct_timezone(self) -> None:
        """A valid timezone should be returned."""
        with patch.dict("os.environ", {"TIMEZONE": "Europe/Stockholm"}, clear=True):
            tz: pytz.BaseTzInfo = get_scheduler_timezone()

        assert isinstance(tz, pytz.BaseTzInfo)
        assert str(tz) == "Europe/Stockholm"

    def test_uses_utc_as_fallback(self) -> None:
        """UTC should work as a timezone value."""
        with patch.dict("os.environ", {"TIMEZONE": "UTC"}, clear=True):
            tz = get_scheduler_timezone()

        assert isinstance(tz, pytz.BaseTzInfo)
        assert str(tz) == "UTC"

    def test_raises_on_missing_env_var(self) -> None:
        """A missing TIMEZONE env var should raise ValueError."""
        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValueError, match="Missing timezone"):
            get_scheduler_timezone()

    def test_raises_on_invalid_timezone(self) -> None:
        """An invalid timezone string should raise ValueError."""
        with patch.dict("os.environ", {"TIMEZONE": "Fake/Timezone"}, clear=True), pytest.raises(ValueError, match="Invalid timezone"):
            get_scheduler_timezone()

    def test_caches_result_on_subsequent_calls(self) -> None:
        """After the first call, the same cached object should be returned."""
        with patch.dict("os.environ", {"TIMEZONE": "Asia/Tokyo"}, clear=True):
            first = get_scheduler_timezone()
            second = get_scheduler_timezone()

        assert first is second, "Expected the same cached timezone object"

    def test_does_not_reload_from_env_on_cache_hit(self) -> None:
        """When the cache is populated, the env var should not be read again."""
        with patch.dict("os.environ", {"TIMEZONE": "America/New_York"}, clear=True):
            first = get_scheduler_timezone()

            # Change the env var after caching
            with patch.dict("os.environ", {"TIMEZONE": "Europe/London"}, clear=True):
                second = get_scheduler_timezone()

        # Should still be the cached New York timezone
        assert str(first) == "America/New_York"
        assert str(second) == "America/New_York"
        assert first is second

    def test_dst_timezone(self) -> None:
        """A timezone with DST should be handled correctly."""
        with patch.dict("os.environ", {"TIMEZONE": "Europe/Berlin"}, clear=True):
            tz = get_scheduler_timezone()

        assert isinstance(tz, pytz.BaseTzInfo)
        # Europe/Berlin has DST transitions: June offset should be UTC+2, January offset UTC+1
        from datetime import UTC, datetime

        summer = datetime(2026, 6, 1, tzinfo=UTC).astimezone(tz)
        winter = datetime(2026, 1, 1, tzinfo=UTC).astimezone(tz)
        assert summer.utcoffset() != winter.utcoffset()

    def test_pytz_type(self) -> None:
        """The returned object should be a pytz timezone (used by APScheduler)."""
        with patch.dict("os.environ", {"TIMEZONE": "UTC"}, clear=True):
            tz = get_scheduler_timezone()

        assert isinstance(tz, pytz.BaseTzInfo)
        # Verify it can be used with APScheduler's AsyncIOScheduler
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = AsyncIOScheduler(timezone=tz)
        # APScheduler may convert pytz to zoneinfo internally; just verify no crash
        assert scheduler.timezone is not None
