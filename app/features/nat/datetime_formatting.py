from __future__ import annotations

from datetime import datetime

from app.core.config import settings


def format_task_datetime_for_display_value(value: datetime, *, fmt: str) -> str:
    naive_value = value.replace(tzinfo=None) if value.tzinfo is not None else value
    return naive_value.strftime(fmt)


def format_task_datetime_for_display(value: datetime) -> str:
    return format_task_datetime_for_display_value(
        value,
        fmt=settings.NAT_TASK_DISPLAY_DATETIME_FORMAT,
    )
