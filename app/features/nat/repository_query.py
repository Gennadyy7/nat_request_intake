from sqlalchemy import ColumnElement, asc, desc
from sqlalchemy.orm import InstrumentedAttribute

from app.features.nat.models import NatBatch, NatIntake, NatIntakeRowError, NatTask
from app.features.nat.query_params import (
    NatBatchFilters,
    NatIntakeFilters,
    NatTaskFilters,
    SortOrder,
    SortParams,
)


def escape_ilike_pattern(value: str) -> str:
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


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
    if filters.intake_id is not None:
        clauses.append(NatIntake.id == filters.intake_id)
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
    return clauses


def build_task_filter_clauses(
    filters: NatTaskFilters,
) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if filters.batch_id is not None:
        clauses.append(NatTask.batch_id == filters.batch_id)
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


def order_by_sort_column(
    column: InstrumentedAttribute[object],
    sort_order: SortOrder,
) -> ColumnElement[object]:
    return desc(column) if sort_order == 'desc' else asc(column)


def row_error_sort_expression(
    sort_order: SortOrder,
) -> ColumnElement[object]:
    return order_by_sort_column(NatIntakeRowError.row_number, sort_order)
