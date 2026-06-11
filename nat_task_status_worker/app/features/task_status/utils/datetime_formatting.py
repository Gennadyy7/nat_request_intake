from __future__ import annotations

from datetime import datetime


def format_task_datetime_for_webapi_value(value: datetime, *, fmt: str) -> str:
    naive_value = value.replace(tzinfo=None) if value.tzinfo is not None else value
    return naive_value.strftime(fmt)


def format_task_datetime_for_webapi(value: datetime) -> str:
    from nat_task_status_worker.app.core.config import settings

    return format_task_datetime_for_webapi_value(
        value,
        fmt=settings.NAT_WEBAPI_DATETIME_FORMAT,
    )
