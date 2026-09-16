from typing import Literal, NamedTuple

from fastapi import HTTPException, status

from app.features.nat.constants import (
    TASK_FILTER_NULL_SENTINEL,
    ApiErrorCode,
)
from app.features.nat.messages import get_message

TaskIntFilterField = Literal['status', 'nat_request_id']


class TaskIntFilter(NamedTuple):
    eq_value: int | None
    is_null: bool


def parse_task_int_filter(
    raw: str | None,
    *,
    field: TaskIntFilterField,
) -> TaskIntFilter:
    if raw is None:
        return TaskIntFilter(eq_value=None, is_null=False)
    if raw == TASK_FILTER_NULL_SENTINEL:
        return TaskIntFilter(eq_value=None, is_null=True)
    try:
        return TaskIntFilter(eq_value=int(raw), is_null=False)
    except ValueError as exc:
        error_code = (
            ApiErrorCode.INVALID_FILTER_TASK_STATUS
            if field == 'status'
            else ApiErrorCode.INVALID_FILTER_NAT_REQUEST_ID
        )
        param_name = f'filter_{field}'
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                'code': error_code,
                'message': get_message(error_code),
                param_name: raw,
            },
        ) from exc
