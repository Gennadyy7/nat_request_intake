from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from loguru import logger

from intake_result_email_worker.app.core.config import settings

if TYPE_CHECKING:
    from loguru import Logger


def setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        format=(
            '<green>{time:YYYY-MM-DD HH:mm:ss}</green> | '
            '<level>{level: <8}</level> | '
            '<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - '
            '<level>{message}</level>'
        ),
        level=settings.LOG_LEVEL,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )


def get_logger(name: str | None = None) -> Logger:
    if name:
        return logger.bind(name=name)
    return logger
