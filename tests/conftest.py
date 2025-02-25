from __future__ import annotations

import os


def pytest_configure() -> None:
    """Disable Sentry in tests."""
    os.environ["SENTRY_DSN"] = ""
