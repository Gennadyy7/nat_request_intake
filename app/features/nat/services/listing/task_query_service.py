from uuid import UUID

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.datetime_formatting import format_task_datetime_for_display
from app.features.nat.pagination import PaginationParams, build_paginated_response
from app.features.nat.query_params import NatTaskFilters, SortParams
from app.features.nat.repository_records import NatTaskListRecord
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
        records = await self._uow.nat_tasks.list_filtered(
            filters,
            sort,
            limit=pagination.limit,
            offset=pagination.offset,
        )
        items = [self._to_list_item(record) for record in records]
        return build_paginated_response(
            items,
            total_items=total_items,
            page=pagination.page,
            limit=pagination.limit,
        )

    async def get_task(self, task_id: UUID) -> NatTaskDetail | None:
        record = await self._uow.nat_tasks.get_list_record_by_id(task_id)
        if record is None:
            return None
        return self._to_detail(record)

    def _to_list_item(self, record: NatTaskListRecord) -> NatTaskListItem:
        task = record.task
        return NatTaskListItem(
            id=task.id,
            batch_id=task.batch_id,
            intake_number=record.intake_number,
            nat_request_id=task.nat_request_id,
            datetime_from=format_task_datetime_for_display(task.datetime_from),
            datetime_to=format_task_datetime_for_display(task.datetime_to),
            src_xlated=task.src_xlated,
            src_port_xlated=task.src_port_xlated,
            src=task.src,
            src_port=task.src_port,
            dst=task.dst,
            dst_port=task.dst_port,
            region=task.region,
            status=task.status,
            progress=task.progress,
            error=task.error_message,
            created_at=task.created_at,
        )

    def _to_detail(self, record: NatTaskListRecord) -> NatTaskDetail:
        task = record.task
        return NatTaskDetail(
            **self._to_list_item(record).model_dump(),
            count_of_lines=task.count_of_lines,
            nat_file_id=task.nat_file_id,
            file_url=task.file_url,
            file_size=task.file_size,
            file_type=task.file_type,
        )
