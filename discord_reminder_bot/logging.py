import os
import sys

from loguru import logger

log_level: str = os.getenv(key="LOG_LEVEL", default="INFO")
logger.remove()
logger.add(sys.stderr, level=log_level, colorize=True)
