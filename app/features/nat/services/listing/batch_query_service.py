from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.pagination import PaginationParams, build_paginated_response
from app.features.nat.query_params import NatBatchFilters, SortParams
from app.features.nat.repository_records import NatBatchDetailRecord, NatBatchListRecord
from app.features.nat.schemas.batch_list import NatBatchDetail, NatBatchListItem
from app.features.nat.schemas.pagination import PaginatedResponse
from app.features.nat.services.persistence.file_storage import FileStorageService


@dataclass(frozen=True, slots=True)
class BatchSourceFileDescriptor:
    path: Path
    download_filename: str
    media_type: str


@dataclass(frozen=True, slots=True)
class BatchSourceFileResolveResult:
    status: Literal['ok', 'batch_not_found', 'file_not_found']
    descriptor: BatchSourceFileDescriptor | None = None


class BatchQueryService:
    def __init__(
        self,
        *,
        uow: UnitOfWorkProtocol,
        file_storage: FileStorageService,
    ) -> None:
        self._uow = uow
        self._file_storage = file_storage

    async def list_batches(
        self,
        *,
        filters: NatBatchFilters,
        sort: SortParams,
        pagination: PaginationParams,
    ) -> PaginatedResponse[NatBatchListItem]:
        total_items = await self._uow.nat_batches.count_filtered(filters)
        records = await self._uow.nat_batches.list_filtered(
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

    async def get_batch(self, batch_id: UUID) -> NatBatchDetail | None:
        record = await self._uow.nat_batches.get_detail_by_id(batch_id)
        if record is None:
            return None
        return self._to_detail(record)

    async def resolve_source_file(
        self,
        batch_id: UUID,
    ) -> BatchSourceFileResolveResult:
        record = await self._uow.nat_batches.get_detail_by_id(batch_id)
        if record is None:
            return BatchSourceFileResolveResult(status='batch_not_found')

        safe_path = self._file_storage.resolve_safe_path(record.batch.file_name)
        if safe_path is None or not self._file_storage.is_readable_file(safe_path):
            return BatchSourceFileResolveResult(status='file_not_found')

        return BatchSourceFileResolveResult(
            status='ok',
            descriptor=BatchSourceFileDescriptor(
                path=safe_path,
                download_filename=record.original_file_name,
                media_type=self._file_storage.resolve_media_type(
                    record.original_file_name,
                ),
            ),
        )

    def _to_list_item(self, record: NatBatchListRecord) -> NatBatchListItem:
        batch = record.batch
        return NatBatchListItem(
            id=batch.id,
            intake_id=batch.intake_id,
            intake_number=record.intake_number,
            file_name=record.original_file_name,
            row_count=batch.row_count,
            tasks_count=record.tasks_count,
            sender_email=record.sender_email,
            created_at=batch.created_at,
        )

    def _to_detail(self, record: NatBatchDetailRecord) -> NatBatchDetail:
        batch = record.batch
        return NatBatchDetail(
            id=batch.id,
            intake_id=batch.intake_id,
            intake_number=record.intake_number,
            file_name=record.original_file_name,
            stored_file_path=batch.file_name,
            row_count=batch.row_count,
            tasks_count=record.tasks_count,
            sender_email=record.sender_email,
            created_at=batch.created_at,
        )
