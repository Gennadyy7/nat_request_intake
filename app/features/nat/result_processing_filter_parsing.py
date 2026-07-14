from typing import NamedTuple

from fastapi import HTTPException, status

from app.features.nat.constants import (
    TASK_FILTER_NULL_SENTINEL,
    ApiErrorCode,
    NatResultProcessingStatus,
)
from app.features.nat.messages import get_message


class ResultProcessingStatusFilter(NamedTuple):
    eq_value: NatResultProcessingStatus | None
    is_null: bool


def parse_result_processing_status_filter(
    raw: str | None,
) -> ResultProcessingStatusFilter:
    if raw is None:
        return ResultProcessingStatusFilter(eq_value=None, is_null=False)
    if raw == TASK_FILTER_NULL_SENTINEL:
        return ResultProcessingStatusFilter(eq_value=None, is_null=True)
    try:
        return ResultProcessingStatusFilter(
            eq_value=NatResultProcessingStatus(raw),
            is_null=False,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                'code': ApiErrorCode.INVALID_FILTER_RESULT_PROCESSING_STATUS,
                'message': get_message(
                    ApiErrorCode.INVALID_FILTER_RESULT_PROCESSING_STATUS
                ),
                'filter_result_processing_status': raw,
                'allowed': [
                    *[member.value for member in NatResultProcessingStatus],
                    TASK_FILTER_NULL_SENTINEL,
                ],
            },
        ) from exc


def parse_result_processing_list_status_filter(
    raw: str | None,
) -> NatResultProcessingStatus | None:
    """Parse status for /spin/result-processing list (enum only, no null sentinel)."""
    if raw is None:
        return None
    try:
        return NatResultProcessingStatus(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                'code': ApiErrorCode.INVALID_FILTER_RESULT_PROCESSING_STATUS,
                'message': get_message(
                    ApiErrorCode.INVALID_FILTER_RESULT_PROCESSING_STATUS
                ),
                'filter_status': raw,
                'allowed': [member.value for member in NatResultProcessingStatus],
            },
        ) from exc
