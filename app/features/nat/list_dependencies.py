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
    NAT_RESULT_PROCESSING_SORT_COLUMNS,
    NAT_TASK_SORT_COLUMNS,
    NatBatchFilters,
    NatIntakeFilters,
    NatIntakeMonitoringFilters,
    NatResultProcessingFilters,
    NatTaskFilters,
    SortOrder,
    SortParams,
)
from app.features.nat.result_processing_filter_parsing import (
    parse_result_processing_list_status_filter,
    parse_result_processing_status_filter,
)
from app.features.nat.services.listing.task_filter_parsing import parse_task_int_filter


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


def get_nat_result_processing_sort_params(
    sort_by: Annotated[str | None, Query()] = None,
    sort_order: Annotated[str | None, Query()] = None,
) -> SortParams:
    return resolve_sort_params(
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_columns=NAT_RESULT_PROCESSING_SORT_COLUMNS,
        default_sort_by='created_at',
        default_sort_order='desc',
    )


def get_nat_intake_filters(
    filter_intake_id: Annotated[UUID | None, Query()] = None,
    filter_sender_email: Annotated[str | None, Query()] = None,
    filter_file_name: Annotated[str | None, Query()] = None,
    filter_created_at_from: Annotated[datetime | None, Query()] = None,
    filter_created_at_to: Annotated[datetime | None, Query()] = None,
    filter_status: Annotated[str | None, Query()] = None,
    filter_processing_paused: Annotated[bool | None, Query()] = None,
) -> NatIntakeFilters:
    status_value: IntakeStatus | None = None
    if filter_status is not None:
        try:
            status_value = IntakeStatus(filter_status)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    'code': ApiErrorCode.INVALID_FILTER_STATUS,
                    'message': get_message(ApiErrorCode.INVALID_FILTER_STATUS),
                    'filter_status': filter_status,
                    'allowed': [member.value for member in IntakeStatus],
                },
            ) from exc
    return NatIntakeFilters(
        intake_id=filter_intake_id,
        sender_email=filter_sender_email,
        file_name=filter_file_name,
        created_at_from=filter_created_at_from,
        created_at_to=filter_created_at_to,
        status=status_value,
        processing_paused=filter_processing_paused,
    )


def get_nat_intake_monitoring_filters(
    filter_intake_id: Annotated[UUID | None, Query()] = None,
    filter_sender_email: Annotated[str | None, Query()] = None,
    filter_file_name: Annotated[str | None, Query()] = None,
    filter_created_at_from: Annotated[datetime | None, Query()] = None,
    filter_created_at_to: Annotated[datetime | None, Query()] = None,
    filter_status: Annotated[str | None, Query()] = None,
    filter_processing_paused: Annotated[bool | None, Query()] = None,
    filter_result_processing_status: Annotated[str | None, Query()] = None,
) -> NatIntakeMonitoringFilters:
    base_filters = get_nat_intake_filters(
        filter_intake_id=filter_intake_id,
        filter_sender_email=filter_sender_email,
        filter_file_name=filter_file_name,
        filter_created_at_from=filter_created_at_from,
        filter_created_at_to=filter_created_at_to,
        filter_status=filter_status,
        filter_processing_paused=filter_processing_paused,
    )
    result_processing_filter = parse_result_processing_status_filter(
        filter_result_processing_status,
    )
    return NatIntakeMonitoringFilters(
        intake_id=base_filters.intake_id,
        sender_email=base_filters.sender_email,
        file_name=base_filters.file_name,
        created_at_from=base_filters.created_at_from,
        created_at_to=base_filters.created_at_to,
        status=base_filters.status,
        processing_paused=base_filters.processing_paused,
        result_processing_status=result_processing_filter.eq_value,
        result_processing_status_is_null=result_processing_filter.is_null,
    )


def get_nat_batch_filters(
    filter_batch_id: Annotated[UUID | None, Query()] = None,
    filter_sender_email: Annotated[str | None, Query()] = None,
    filter_file_name: Annotated[str | None, Query()] = None,
    filter_created_at_from: Annotated[datetime | None, Query()] = None,
    filter_created_at_to: Annotated[datetime | None, Query()] = None,
    filter_row_count_min: Annotated[int | None, Query(ge=0)] = None,
    filter_row_count_max: Annotated[int | None, Query(ge=0)] = None,
) -> NatBatchFilters:
    return NatBatchFilters(
        batch_id=filter_batch_id,
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
                'code': ApiErrorCode.INVALID_SORT_ORDER,
                'message': get_message(ApiErrorCode.INVALID_SORT_ORDER),
                'sort_order': sort_order,
                'allowed': ['asc', 'desc'],
            },
        )
    return 'asc' if sort_order == 'asc' else 'desc'


def get_nat_task_filters(
    filter_batch_id: Annotated[UUID | None, Query()] = None,
    filter_status: Annotated[str | None, Query()] = None,
    filter_nat_request_id: Annotated[str | None, Query()] = None,
    filter_region: Annotated[str | None, Query()] = None,
    filter_created_at_from: Annotated[datetime | None, Query()] = None,
    filter_created_at_to: Annotated[datetime | None, Query()] = None,
) -> NatTaskFilters:
    status_filter = parse_task_int_filter(filter_status, field='status')
    nat_request_id_filter = parse_task_int_filter(
        filter_nat_request_id,
        field='nat_request_id',
    )
    return NatTaskFilters(
        batch_id=filter_batch_id,
        status=status_filter.eq_value,
        status_is_null=status_filter.is_null,
        nat_request_id=nat_request_id_filter.eq_value,
        nat_request_id_is_null=nat_request_id_filter.is_null,
        region=filter_region,
        created_at_from=filter_created_at_from,
        created_at_to=filter_created_at_to,
    )


def get_nat_result_processing_filters(
    filter_result_processing_id: Annotated[UUID | None, Query()] = None,
    filter_batch_id: Annotated[UUID | None, Query()] = None,
    filter_status: Annotated[str | None, Query()] = None,
    filter_created_at_from: Annotated[datetime | None, Query()] = None,
    filter_created_at_to: Annotated[datetime | None, Query()] = None,
    filter_completed_at_from: Annotated[datetime | None, Query()] = None,
    filter_completed_at_to: Annotated[datetime | None, Query()] = None,
) -> NatResultProcessingFilters:
    return NatResultProcessingFilters(
        result_processing_id=filter_result_processing_id,
        batch_id=filter_batch_id,
        status=parse_result_processing_list_status_filter(filter_status),
        created_at_from=filter_created_at_from,
        created_at_to=filter_created_at_to,
        completed_at_from=filter_completed_at_from,
        completed_at_to=filter_completed_at_to,
    )
