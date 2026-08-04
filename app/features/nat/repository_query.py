from sqlalchemy import ColumnElement, asc, desc, exists, or_, select
from sqlalchemy.orm import InstrumentedAttribute

from app.features.assomi.models import AssomiTask
from app.features.nat.models import (
    GLOBAL_PROCESSING_SINGLETON_ID,
    NatBatch,
    NatGlobalProcessing,
    NatIntake,
    NatIntakeRowError,
    NatResultProcessingTask,
    NatTask,
)
from app.features.nat.query_params import (
    NatBatchFilters,
    NatIntakeFilters,
    NatIntakeMonitoringFilters,
    NatResultProcessingFilters,
    NatTaskFilters,
    SortOrder,
    SortParams,
)


def escape_ilike_pattern(value: str) -> str:
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def global_processing_not_paused() -> ColumnElement[bool]:
    return ~exists(
        select(NatGlobalProcessing.id).where(
            NatGlobalProcessing.id == GLOBAL_PROCESSING_SINGLETON_ID,
            NatGlobalProcessing.processing_paused.is_(True),
        )
    )


def build_intake_filter_clauses(
    filters: NatIntakeFilters,
) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if filters.sender_email is not None:
        pattern = f'%{escape_ilike_pattern(filters.sender_email)}%'
        clauses.append(NatIntake.sender_email.ilike(pattern))
    if filters.file_name is not None:
        pattern = f'%{escape_ilike_pattern(filters.file_name)}%'
        clauses.append(NatIntake.file_name.ilike(pattern))
    if filters.created_at_from is not None:
        clauses.append(NatIntake.created_at >= filters.created_at_from)
    if filters.created_at_to is not None:
        clauses.append(NatIntake.created_at <= filters.created_at_to)
    if filters.status is not None:
        clauses.append(NatIntake.status == filters.status.value)
    if filters.source is not None:
        clauses.append(NatIntake.source == filters.source.value)
    if filters.intake_id is not None:
        clauses.append(NatIntake.id == filters.intake_id)
    if filters.intake_number is not None:
        clauses.append(NatIntake.number == filters.intake_number)
    if filters.processing_paused is True:
        clauses.append(NatBatch.id.is_not(None))
        clauses.append(NatBatch.processing_paused.is_(True))
    elif filters.processing_paused is False:
        clauses.append(
            or_(
                NatBatch.id.is_(None),
                NatBatch.processing_paused.is_(False),
            )
        )
    return clauses


def intake_list_requires_batch_join(filters: NatIntakeFilters) -> bool:
    return filters.processing_paused is not None


def monitoring_requires_result_processing_join(
    filters: NatIntakeMonitoringFilters,
) -> bool:
    return (
        filters.result_processing_status_is_null
        or filters.result_processing_status is not None
    )


def monitoring_requires_assomi_join(
    filters: NatIntakeMonitoringFilters,
) -> bool:
    return filters.assomi_status_is_null or filters.assomi_status is not None


def build_result_processing_filter_clauses(
    filters: NatIntakeMonitoringFilters,
) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if filters.result_processing_status_is_null:
        clauses.append(NatResultProcessingTask.id.is_(None))
    elif filters.result_processing_status is not None:
        clauses.append(
            NatResultProcessingTask.status == filters.result_processing_status.value
        )
    return clauses


def build_assomi_filter_clauses(
    filters: NatIntakeMonitoringFilters,
) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if filters.assomi_status_is_null:
        clauses.append(AssomiTask.id.is_(None))
    elif filters.assomi_status is not None:
        clauses.append(AssomiTask.status == filters.assomi_status.value)
    return clauses


def build_batch_filter_clauses(
    filters: NatBatchFilters,
) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if filters.sender_email is not None:
        pattern = f'%{escape_ilike_pattern(filters.sender_email)}%'
        clauses.append(NatIntake.sender_email.ilike(pattern))
    if filters.file_name is not None:
        pattern = f'%{escape_ilike_pattern(filters.file_name)}%'
        clauses.append(NatIntake.file_name.ilike(pattern))
    if filters.created_at_from is not None:
        clauses.append(NatBatch.created_at >= filters.created_at_from)
    if filters.created_at_to is not None:
        clauses.append(NatBatch.created_at <= filters.created_at_to)
    if filters.row_count_min is not None:
        clauses.append(NatBatch.row_count >= filters.row_count_min)
    if filters.row_count_max is not None:
        clauses.append(NatBatch.row_count <= filters.row_count_max)
    if filters.batch_id is not None:
        clauses.append(NatBatch.id == filters.batch_id)
    if filters.intake_number is not None:
        clauses.append(NatIntake.number == filters.intake_number)
    return clauses


def build_task_filter_clauses(
    filters: NatTaskFilters,
) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if filters.batch_id is not None:
        clauses.append(NatTask.batch_id == filters.batch_id)
    if filters.intake_number is not None:
        clauses.append(NatIntake.number == filters.intake_number)
    if filters.status_is_null:
        clauses.append(NatTask.status.is_(None))
    elif filters.status is not None:
        clauses.append(NatTask.status == filters.status)
    if filters.nat_request_id_is_null:
        clauses.append(NatTask.nat_request_id.is_(None))
    elif filters.nat_request_id is not None:
        clauses.append(NatTask.nat_request_id == filters.nat_request_id)
    if filters.region is not None:
        clauses.append(NatTask.region == filters.region)
    if filters.created_at_from is not None:
        clauses.append(NatTask.created_at >= filters.created_at_from)
    if filters.created_at_to is not None:
        clauses.append(NatTask.created_at <= filters.created_at_to)
    return clauses


def task_list_requires_intake_join(filters: NatTaskFilters) -> bool:
    return filters.intake_number is not None


def build_result_processing_list_filter_clauses(
    filters: NatResultProcessingFilters,
) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if filters.result_processing_id is not None:
        clauses.append(NatResultProcessingTask.id == filters.result_processing_id)
    if filters.batch_id is not None:
        clauses.append(NatResultProcessingTask.nat_batch_id == filters.batch_id)
    if filters.intake_number is not None:
        clauses.append(NatIntake.number == filters.intake_number)
    if filters.status is not None:
        clauses.append(NatResultProcessingTask.status == filters.status.value)
    if filters.created_at_from is not None:
        clauses.append(NatResultProcessingTask.created_at >= filters.created_at_from)
    if filters.created_at_to is not None:
        clauses.append(NatResultProcessingTask.created_at <= filters.created_at_to)
    if filters.completed_at_from is not None:
        clauses.append(
            NatResultProcessingTask.completed_at >= filters.completed_at_from
        )
    if filters.completed_at_to is not None:
        clauses.append(NatResultProcessingTask.completed_at <= filters.completed_at_to)
    return clauses


def result_processing_list_requires_intake_join(
    filters: NatResultProcessingFilters,
) -> bool:
    return filters.intake_number is not None


def intake_sort_column(sort: SortParams) -> InstrumentedAttribute[object]:
    return {
        'created_at': NatIntake.created_at,
        'file_name': NatIntake.file_name,
        'sender_email': NatIntake.sender_email,
    }[sort.sort_by]


def batch_sort_column(sort: SortParams) -> InstrumentedAttribute[object]:
    if sort.sort_by in {'sender_email', 'file_name'}:
        return {
            'sender_email': NatIntake.sender_email,
            'file_name': NatIntake.file_name,
        }[sort.sort_by]
    return {
        'created_at': NatBatch.created_at,
        'row_count': NatBatch.row_count,
    }[sort.sort_by]


def task_sort_column(sort: SortParams) -> InstrumentedAttribute[object]:
    return {
        'created_at': NatTask.created_at,
        'status': NatTask.status,
        'batch_id': NatTask.batch_id,
    }[sort.sort_by]


def result_processing_sort_column(sort: SortParams) -> InstrumentedAttribute[object]:
    return {
        'created_at': NatResultProcessingTask.created_at,
        'status': NatResultProcessingTask.status,
        'batch_id': NatResultProcessingTask.nat_batch_id,
        'completed_at': NatResultProcessingTask.completed_at,
    }[sort.sort_by]


def order_by_sort_column(
    column: InstrumentedAttribute[object],
    sort_order: SortOrder,
) -> ColumnElement[object]:
    return desc(column) if sort_order == 'desc' else asc(column)


def row_error_sort_expression(
    sort_order: SortOrder,
) -> ColumnElement[object]:
    return order_by_sort_column(NatIntakeRowError.row_number, sort_order)
