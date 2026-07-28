from sqlalchemy import ColumnElement
from sqlalchemy.orm import InstrumentedAttribute

from app.features.assomi.models import AssomiTask
from app.features.assomi.query_params import AssomiTaskFilters
from app.features.nat.models import NatIntake
from app.features.nat.query_params import SortParams


def build_assomi_list_filter_clauses(
    filters: AssomiTaskFilters,
) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if filters.assomi_id is not None:
        clauses.append(AssomiTask.id == filters.assomi_id)
    if filters.aggregation_task_id is not None:
        clauses.append(AssomiTask.aggregation_task_id == filters.aggregation_task_id)
    if filters.batch_id is not None:
        clauses.append(AssomiTask.nat_batch_id == filters.batch_id)
    if filters.intake_number is not None:
        clauses.append(NatIntake.number == filters.intake_number)
    if filters.status is not None:
        clauses.append(AssomiTask.status == filters.status.value)
    if filters.created_at_from is not None:
        clauses.append(AssomiTask.created_at >= filters.created_at_from)
    if filters.created_at_to is not None:
        clauses.append(AssomiTask.created_at <= filters.created_at_to)
    if filters.completed_at_from is not None:
        clauses.append(AssomiTask.completed_at >= filters.completed_at_from)
    if filters.completed_at_to is not None:
        clauses.append(AssomiTask.completed_at <= filters.completed_at_to)
    return clauses


def assomi_list_requires_intake_join(filters: AssomiTaskFilters) -> bool:
    return filters.intake_number is not None


def assomi_sort_column(sort: SortParams) -> InstrumentedAttribute[object]:
    return {
        'created_at': AssomiTask.created_at,
        'status': AssomiTask.status,
        'batch_id': AssomiTask.nat_batch_id,
        'completed_at': AssomiTask.completed_at,
    }[sort.sort_by]
