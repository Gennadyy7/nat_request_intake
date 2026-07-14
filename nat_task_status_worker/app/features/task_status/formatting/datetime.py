from datetime import datetime


def format_task_datetime_for_webapi_value(value: datetime, *, fmt: str) -> str:
    naive_value = value.replace(tzinfo=None) if value.tzinfo is not None else value
    return naive_value.strftime(fmt)
