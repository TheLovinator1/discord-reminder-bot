from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def dockerfile_content() -> str:
    """Read the content of the Dockerfile and return it as a string.

    Returns:
        str: The content of the Dockerfile.
    """
    return Path("Dockerfile").read_text(encoding="utf-8")


def test_volume_exists(dockerfile_content: str) -> None:
    """Test that the volume is set in the Dockerfile."""
    assert_msg = "Volume not set in Dockerfile. This has to always be set to /home/botuser/data/."
    assert 'VOLUME ["/home/botuser/data/"]' in dockerfile_content, assert_msg


def test_env_variables(dockerfile_content: str) -> None:
    """Test that the environment variables for Python are set in the Dockerfile."""
    assert "ENV PYTHONUNBUFFERED=1" in dockerfile_content, "PYTHONUNBUFFERED not set in Dockerfile"
    assert "ENV PYTHONDONTWRITEBYTECODE=1" in dockerfile_content, "PYTHONDONTWRITEBYTECODE not set in Dockerfile"
