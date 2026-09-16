from typing import NamedTuple

from fastapi import HTTPException, status

from app.features.assomi.constants import AssomiApiErrorCode, AssomiTaskStatus
from app.features.assomi.messages import get_message
from app.features.nat.constants import TASK_FILTER_NULL_SENTINEL


class AssomiStatusFilter(NamedTuple):
    eq_value: AssomiTaskStatus | None
    is_null: bool


def parse_assomi_list_status_filter(raw: str | None) -> AssomiTaskStatus | None:
    """Parse status for /assomi list (enum only, no null sentinel)."""
    if raw is None:
        return None
    try:
        return AssomiTaskStatus(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                'code': AssomiApiErrorCode.INVALID_FILTER_ASSOMI_STATUS,
                'message': get_message(AssomiApiErrorCode.INVALID_FILTER_ASSOMI_STATUS),
                'filter_status': raw,
                'allowed': [member.value for member in AssomiTaskStatus],
            },
        ) from exc


def parse_assomi_monitoring_status_filter(raw: str | None) -> AssomiStatusFilter:
    if raw is None:
        return AssomiStatusFilter(eq_value=None, is_null=False)
    if raw == TASK_FILTER_NULL_SENTINEL:
        return AssomiStatusFilter(eq_value=None, is_null=True)
    try:
        return AssomiStatusFilter(
            eq_value=AssomiTaskStatus(raw),
            is_null=False,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                'code': AssomiApiErrorCode.INVALID_FILTER_ASSOMI_STATUS,
                'message': get_message(AssomiApiErrorCode.INVALID_FILTER_ASSOMI_STATUS),
                'filter_assomi_status': raw,
                'allowed': [
                    *[member.value for member in AssomiTaskStatus],
                    TASK_FILTER_NULL_SENTINEL,
                ],
            },
        ) from exc
