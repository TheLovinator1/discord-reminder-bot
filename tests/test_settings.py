"""Tests for the ``settings`` module (scheduler configuration)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler


def test_get_scheduler_default_misfire_grace_time() -> None:
    """When MISFIRE_GRACE_TIME is not set, the default should be 3600."""
    with patch.dict("os.environ", {"TIMEZONE": "UTC"}, clear=True):
        # Re-import to get a fresh scheduler without cached module state interference
        import importlib

        import discord_reminder_bot.settings as settings_mod

        importlib.reload(settings_mod)

        scheduler: AsyncIOScheduler = settings_mod.get_scheduler()

    msg: str = f"Expected default misfire_grace_time of 3600, got {scheduler._job_defaults['misfire_grace_time']}"
    assert scheduler._job_defaults["misfire_grace_time"] == 3600, msg


def test_get_scheduler_custom_misfire_grace_time() -> None:
    """MISFIRE_GRACE_TIME should be read from the environment variable."""
    with patch.dict("os.environ", {"TIMEZONE": "UTC", "MISFIRE_GRACE_TIME": "7200"}, clear=True):
        import importlib

        import discord_reminder_bot.settings as settings_mod

        importlib.reload(settings_mod)

        scheduler: AsyncIOScheduler = settings_mod.get_scheduler()

    msg: str = f"Expected custom misfire_grace_time of 7200, got {scheduler._job_defaults['misfire_grace_time']}"
    assert scheduler._job_defaults["misfire_grace_time"] == 7200, msg


def test_get_scheduler_misfire_grace_time_edge_cases() -> None:
    """Very small and very large MISFIRE_GRACE_TIME values should work."""
    test_cases: list[tuple[str, int]] = [
        ("0", 0),
        ("1", 1),
        ("86400", 86400),  # 24 hours
        ("999999999", 999999999),
    ]

    for env_value, expected in test_cases:
        with patch.dict("os.environ", {"TIMEZONE": "UTC", "MISFIRE_GRACE_TIME": env_value}, clear=True):
            import importlib

            import discord_reminder_bot.settings as settings_mod

            importlib.reload(settings_mod)

            scheduler: AsyncIOScheduler = settings_mod.get_scheduler()

        msg: str = (
            f"Expected misfire_grace_time of {expected} from env value '{env_value}', got {scheduler._job_defaults['misfire_grace_time']}"
        )
        assert scheduler._job_defaults["misfire_grace_time"] == expected, msg


def test_get_scheduler_invalid_misfire_grace_time() -> None:
    """A non-integer MISFIRE_GRACE_TIME should raise ValueError during reload."""
    with patch.dict("os.environ", {"TIMEZONE": "UTC", "MISFIRE_GRACE_TIME": "not_a_number"}, clear=True):
        import importlib

        import discord_reminder_bot.settings as settings_mod

        with pytest.raises(ValueError, match="invalid literal for int"):
            importlib.reload(settings_mod)
