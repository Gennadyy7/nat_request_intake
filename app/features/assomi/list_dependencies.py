from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Query

from app.features.assomi.query_params import ASSOMI_TASK_SORT_COLUMNS, AssomiTaskFilters
from app.features.assomi.status_filter_parsing import parse_assomi_list_status_filter
from app.features.nat.pagination import resolve_sort_params
from app.features.nat.query_params import SortParams


def get_assomi_task_sort_params(
    sort_by: Annotated[str | None, Query()] = None,
    sort_order: Annotated[str | None, Query()] = None,
) -> SortParams:
    return resolve_sort_params(
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_columns=ASSOMI_TASK_SORT_COLUMNS,
        default_sort_by='created_at',
        default_sort_order='desc',
    )


def get_assomi_task_filters(
    filter_assomi_id: Annotated[UUID | None, Query()] = None,
    filter_aggregation_task_id: Annotated[UUID | None, Query()] = None,
    filter_batch_id: Annotated[UUID | None, Query()] = None,
    filter_intake_number: Annotated[int | None, Query(ge=1)] = None,
    filter_status: Annotated[str | None, Query()] = None,
    filter_created_at_from: Annotated[datetime | None, Query()] = None,
    filter_created_at_to: Annotated[datetime | None, Query()] = None,
    filter_completed_at_from: Annotated[datetime | None, Query()] = None,
    filter_completed_at_to: Annotated[datetime | None, Query()] = None,
) -> AssomiTaskFilters:
    return AssomiTaskFilters(
        assomi_id=filter_assomi_id,
        aggregation_task_id=filter_aggregation_task_id,
        batch_id=filter_batch_id,
        intake_number=filter_intake_number,
        status=parse_assomi_list_status_filter(filter_status),
        created_at_from=filter_created_at_from,
        created_at_to=filter_created_at_to,
        completed_at_from=filter_completed_at_from,
        completed_at_to=filter_completed_at_to,
    )
