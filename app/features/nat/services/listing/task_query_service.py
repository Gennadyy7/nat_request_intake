from uuid import UUID

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.models import NatTask
from app.features.nat.pagination import PaginationParams, build_paginated_response
from app.features.nat.query_params import NatTaskFilters, SortParams
from app.features.nat.schemas.pagination import PaginatedResponse
from app.features.nat.schemas.task_list import NatTaskDetail, NatTaskListItem


class TaskQueryService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def list_tasks(
        self,
        *,
        filters: NatTaskFilters,
        sort: SortParams,
        pagination: PaginationParams,
    ) -> PaginatedResponse[NatTaskListItem]:
        total_items = await self._uow.nat_tasks.count_filtered(filters)
        tasks = await self._uow.nat_tasks.list_filtered(
            filters,
            sort,
            limit=pagination.limit,
            offset=pagination.offset,
        )
        items = [self._to_list_item(task) for task in tasks]
        return build_paginated_response(
            items,
            total_items=total_items,
            page=pagination.page,
            limit=pagination.limit,
        )

    async def get_task(self, task_id: UUID) -> NatTaskDetail | None:
        task = await self._uow.nat_tasks.get_by_id(task_id)
        if task is None:
            return None
        return self._to_detail(task)

    def _to_list_item(self, task: NatTask) -> NatTaskListItem:
        return NatTaskListItem.model_validate(task)

    def _to_detail(self, task: NatTask) -> NatTaskDetail:
        return NatTaskDetail.model_validate(self._to_list_item(task).model_dump())
