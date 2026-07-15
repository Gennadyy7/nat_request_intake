from dataclasses import dataclass
from uuid import UUID

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.constants import (
    NatResultProcessingStatus,
    ResultProcessingGetStatus,
)
from app.features.nat.pagination import PaginationParams, build_paginated_response
from app.features.nat.query_params import NatResultProcessingFilters, SortParams
from app.features.nat.repository_records import NatResultProcessingListRecord
from app.features.nat.schemas.pagination import PaginatedResponse
from app.features.nat.schemas.result_processing import (
    NatResultProcessingDetail,
    NatResultProcessingListItem,
)


@dataclass(frozen=True, slots=True)
class ResultProcessingGetResult:
    status: ResultProcessingGetStatus
    detail: NatResultProcessingDetail | None = None


class ResultProcessingQueryService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def list_result_processing(
        self,
        *,
        filters: NatResultProcessingFilters,
        sort: SortParams,
        pagination: PaginationParams,
    ) -> PaginatedResponse[NatResultProcessingListItem]:
        total_items = await self._uow.nat_result_processing_tasks.count_filtered(
            filters
        )
        records = await self._uow.nat_result_processing_tasks.list_filtered(
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

    async def get_by_id(
        self,
        result_processing_id: UUID,
    ) -> NatResultProcessingDetail | None:
        record = await self._uow.nat_result_processing_tasks.get_list_record_by_id(
            result_processing_id
        )
        if record is None:
            return None
        return self._to_detail(record)

    async def get_by_batch_id(self, batch_id: UUID) -> ResultProcessingGetResult:
        batch = await self._uow.nat_batches.get_by_id(batch_id)
        if batch is None:
            return ResultProcessingGetResult(
                status=ResultProcessingGetStatus.BATCH_NOT_FOUND,
            )

        record = (
            await self._uow.nat_result_processing_tasks.get_list_record_by_batch_id(
                batch_id
            )
        )
        if record is None:
            return ResultProcessingGetResult(
                status=ResultProcessingGetStatus.RESULT_PROCESSING_NOT_FOUND,
            )

        return ResultProcessingGetResult(
            status=ResultProcessingGetStatus.OK,
            detail=self._to_detail(record),
        )

    def _to_list_item(
        self,
        record: NatResultProcessingListRecord,
    ) -> NatResultProcessingListItem:
        task = record.task
        return NatResultProcessingListItem(
            id=task.id,
            batch_id=task.nat_batch_id,
            intake_number=record.intake_number,
            status=NatResultProcessingStatus(task.status),
            matched_count=task.matched_count,
            total_to_match=task.total_to_match,
            total_lines=task.total_lines,
            error_message=task.error_message,
            created_at=task.created_at,
            completed_at=task.completed_at,
        )

    def _to_detail(
        self,
        record: NatResultProcessingListRecord,
    ) -> NatResultProcessingDetail:
        task = record.task
        return NatResultProcessingDetail(
            **self._to_list_item(record).model_dump(),
            aggregated_file_path=task.aggregated_file_path,
            spin_matched_file_path=task.spin_matched_file_path,
        )
