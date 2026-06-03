from __future__ import annotations

import os


def pytest_configure() -> None:
    """Disable Sentry and set a default timezone in tests."""
    os.environ.setdefault("TIMEZONE", "UTC")
    os.environ["SENTRY_DSN"] = ""
