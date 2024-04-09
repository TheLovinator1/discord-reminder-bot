from __future__ import annotations

import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from loguru import logger

load_dotenv(dotenv_path=find_dotenv(), verbose=True)


# Discord webhook url for error messages
webhook_url: str = os.getenv(key="WEBHOOK_URL", default="")
if not webhook_url:
    logger.warning(
        "No webhook url configured. You will not receive any error messages.",
    )

# Get the bot token from the environment or raise an exception
bot_token: str = os.getenv(key="BOT_TOKEN", default="")
if not bot_token:
    err_msg = "Missing bot token. Please set the BOT_TOKEN environment variable or add it to .env."  # noqa: E501
    raise ValueError(err_msg)


# Where we store the data
data_dir_env: str | None = os.getenv("DATA_DIR")
DATA_DIR: Path = Path(data_dir_env) if data_dir_env else Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
