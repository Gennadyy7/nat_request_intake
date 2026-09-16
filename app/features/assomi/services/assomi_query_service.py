from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.assomi.constants import AssomiTaskStatus
from app.features.assomi.query_params import AssomiTaskFilters
from app.features.assomi.repository_records import AssomiTaskListRecord
from app.features.assomi.schemas import AssomiTaskDetail, AssomiTaskListItem
from app.features.nat.pagination import PaginationParams, build_paginated_response
from app.features.nat.query_params import SortParams
from app.features.nat.schemas.pagination import PaginatedResponse
from app.features.nat.services.persistence.file_storage import FileStorageService

AssomiFileResolveStatus = Literal[
    'ok',
    'not_found',
    'not_ready',
    'file_not_found',
]


@dataclass(frozen=True, slots=True)
class AssomiFileDescriptor:
    path: Path
    download_filename: str
    media_type: str


@dataclass(frozen=True, slots=True)
class AssomiFileResolveResult:
    status: AssomiFileResolveStatus
    descriptor: AssomiFileDescriptor | None = None


class AssomiQueryService:
    def __init__(
        self,
        *,
        uow: UnitOfWorkProtocol,
        file_storage: FileStorageService,
    ) -> None:
        self._uow = uow
        self._file_storage = file_storage

    async def list_assomi_tasks(
        self,
        *,
        filters: AssomiTaskFilters,
        sort: SortParams,
        pagination: PaginationParams,
    ) -> PaginatedResponse[AssomiTaskListItem]:
        total_items = await self._uow.assomi_tasks.count_filtered(filters)
        records = await self._uow.assomi_tasks.list_filtered(
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

    async def get_by_id(self, assomi_task_id: UUID) -> AssomiTaskDetail | None:
        record = await self._uow.assomi_tasks.get_list_record_by_id(assomi_task_id)
        if record is None:
            return None
        return self._to_detail(record)

    async def resolve_file(self, assomi_task_id: UUID) -> AssomiFileResolveResult:
        record = await self._uow.assomi_tasks.get_list_record_by_id(assomi_task_id)
        if record is None:
            return AssomiFileResolveResult(status='not_found')

        task = record.task
        if task.status != AssomiTaskStatus.COMPLETED.value:
            return AssomiFileResolveResult(status='not_ready')

        if not task.output_path:
            return AssomiFileResolveResult(status='file_not_found')

        safe_path = self._file_storage.resolve_safe_path(task.output_path)
        if safe_path is None or not self._file_storage.is_readable_file(safe_path):
            return AssomiFileResolveResult(status='file_not_found')

        download_filename = safe_path.name
        return AssomiFileResolveResult(
            status='ok',
            descriptor=AssomiFileDescriptor(
                path=safe_path,
                download_filename=download_filename,
                media_type=self._file_storage.resolve_media_type(download_filename),
            ),
        )

    def _to_list_item(self, record: AssomiTaskListRecord) -> AssomiTaskListItem:
        task = record.task
        return AssomiTaskListItem(
            id=task.id,
            aggregation_task_id=task.aggregation_task_id,
            batch_id=task.nat_batch_id,
            intake_number=record.intake_number,
            status=AssomiTaskStatus(task.status),
            found_count=task.found_count,
            missing_count=task.missing_count,
            error_message=task.error_message,
            created_at=task.created_at,
            completed_at=task.completed_at,
        )

    def _to_detail(self, record: AssomiTaskListRecord) -> AssomiTaskDetail:
        return AssomiTaskDetail(
            **self._to_list_item(record).model_dump(),
        )
