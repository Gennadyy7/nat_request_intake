from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import HTTPException, Query, status

from app.features.nat.constants import ApiErrorCode, IntakeStatus
from app.features.nat.messages import get_message
from app.features.nat.pagination import (
    PaginationParams,
    build_pagination_params,
    resolve_sort_params,
)
from app.features.nat.query_params import (
    NAT_BATCH_SORT_COLUMNS,
    NAT_INTAKE_SORT_COLUMNS,
    NAT_TASK_SORT_COLUMNS,
    NatBatchFilters,
    NatIntakeFilters,
    NatTaskFilters,
    SortOrder,
    SortParams,
)


def get_pagination_params(
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int | None, Query(ge=1)] = None,
) -> PaginationParams:
    return build_pagination_params(page=page, requested_limit=limit)


def get_nat_intake_sort_params(
    sort_by: Annotated[str | None, Query()] = None,
    sort_order: Annotated[str | None, Query()] = None,
) -> SortParams:
    return resolve_sort_params(
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_columns=NAT_INTAKE_SORT_COLUMNS,
        default_sort_by='created_at',
        default_sort_order='desc',
    )


def get_nat_batch_sort_params(
    sort_by: Annotated[str | None, Query()] = None,
    sort_order: Annotated[str | None, Query()] = None,
) -> SortParams:
    return resolve_sort_params(
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_columns=NAT_BATCH_SORT_COLUMNS,
        default_sort_by='created_at',
        default_sort_order='desc',
    )


def get_nat_task_sort_params(
    sort_by: Annotated[str | None, Query()] = None,
    sort_order: Annotated[str | None, Query()] = None,
) -> SortParams:
    return resolve_sort_params(
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_columns=NAT_TASK_SORT_COLUMNS,
        default_sort_by='created_at',
        default_sort_order='desc',
    )


def get_nat_intake_filters(
    filter_sender_email: Annotated[str | None, Query()] = None,
    filter_file_name: Annotated[str | None, Query()] = None,
    filter_created_at_from: Annotated[datetime | None, Query()] = None,
    filter_created_at_to: Annotated[datetime | None, Query()] = None,
    filter_status: Annotated[str | None, Query()] = None,
) -> NatIntakeFilters:
    status_value: IntakeStatus | None = None
    if filter_status is not None:
        try:
            status_value = IntakeStatus(filter_status)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    'error_code': ApiErrorCode.INVALID_FILTER_STATUS,
                    'message': get_message(ApiErrorCode.INVALID_FILTER_STATUS),
                    'filter_status': filter_status,
                    'allowed': [member.value for member in IntakeStatus],
                },
            ) from exc
    return NatIntakeFilters(
        sender_email=filter_sender_email,
        file_name=filter_file_name,
        created_at_from=filter_created_at_from,
        created_at_to=filter_created_at_to,
        status=status_value,
    )


def get_nat_batch_filters(
    filter_sender_email: Annotated[str | None, Query()] = None,
    filter_file_name: Annotated[str | None, Query()] = None,
    filter_created_at_from: Annotated[datetime | None, Query()] = None,
    filter_created_at_to: Annotated[datetime | None, Query()] = None,
    filter_row_count_min: Annotated[int | None, Query(ge=0)] = None,
    filter_row_count_max: Annotated[int | None, Query(ge=0)] = None,
) -> NatBatchFilters:
    return NatBatchFilters(
        sender_email=filter_sender_email,
        file_name=filter_file_name,
        created_at_from=filter_created_at_from,
        created_at_to=filter_created_at_to,
        row_count_min=filter_row_count_min,
        row_count_max=filter_row_count_max,
    )


def get_nat_intake_row_errors_sort_order(
    sort_order: Annotated[str | None, Query()] = None,
) -> SortOrder:
    if sort_order is None:
        return 'asc'
    if sort_order not in {'asc', 'desc'}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                'error_code': ApiErrorCode.INVALID_SORT_ORDER,
                'message': get_message(ApiErrorCode.INVALID_SORT_ORDER),
                'sort_order': sort_order,
                'allowed': ['asc', 'desc'],
            },
        )
    return 'asc' if sort_order == 'asc' else 'desc'


def _raise_invalid_filter_combination_error(
    *,
    field: str,
    conflicting_params: list[str],
) -> None:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            'error_code': ApiErrorCode.INVALID_FILTER_COMBINATION,
            'message': get_message(ApiErrorCode.INVALID_FILTER_COMBINATION),
            'field': field,
            'conflicting_params': conflicting_params,
        },
    )


def get_nat_task_filters(
    filter_batch_id: Annotated[UUID | None, Query()] = None,
    filter_status: Annotated[int | None, Query()] = None,
    filter_status_is_null: Annotated[bool, Query()] = False,
    filter_nat_request_id: Annotated[int | None, Query()] = None,
    filter_nat_request_id_is_null: Annotated[bool, Query()] = False,
    filter_region: Annotated[str | None, Query()] = None,
    filter_created_at_from: Annotated[datetime | None, Query()] = None,
    filter_created_at_to: Annotated[datetime | None, Query()] = None,
) -> NatTaskFilters:
    if filter_status_is_null and filter_status is not None:
        _raise_invalid_filter_combination_error(
            field='status',
            conflicting_params=['filter_status', 'filter_status_is_null'],
        )
    if filter_nat_request_id_is_null and filter_nat_request_id is not None:
        _raise_invalid_filter_combination_error(
            field='nat_request_id',
            conflicting_params=[
                'filter_nat_request_id',
                'filter_nat_request_id_is_null',
            ],
        )
    return NatTaskFilters(
        batch_id=filter_batch_id,
        status=filter_status,
        status_is_null=filter_status_is_null,
        nat_request_id=filter_nat_request_id,
        nat_request_id_is_null=filter_nat_request_id_is_null,
        region=filter_region,
        created_at_from=filter_created_at_from,
        created_at_to=filter_created_at_to,
    )
