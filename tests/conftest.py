from __future__ import annotations

import os


def pytest_configure() -> None:
    """Ignore Sentry when running tests."""
    os.environ["SENTRY_DSN"] = ""
