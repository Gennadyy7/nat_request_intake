from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.constants import NatResultProcessingStatus
from app.features.nat.models import NatResultProcessingTask
from app.features.nat.schemas.result_processing import NatResultProcessingDetail


@dataclass(frozen=True, slots=True)
class ResultProcessingGetResult:
    status: Literal['ok', 'batch_not_found', 'not_found']
    detail: NatResultProcessingDetail | None = None


class ResultProcessingQueryService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def get_by_batch_id(self, batch_id: UUID) -> ResultProcessingGetResult:
        batch = await self._uow.nat_batches.get_by_id(batch_id)
        if batch is None:
            return ResultProcessingGetResult(status='batch_not_found')

        task = await self._uow.nat_result_processing_tasks.get_by_batch_id(batch_id)
        if task is None:
            return ResultProcessingGetResult(status='not_found')

        return ResultProcessingGetResult(
            status='ok',
            detail=self._to_detail(task),
        )

    def _to_detail(self, task: NatResultProcessingTask) -> NatResultProcessingDetail:
        return NatResultProcessingDetail(
            id=task.id,
            batch_id=task.nat_batch_id,
            status=NatResultProcessingStatus(task.status),
            matched_count=task.matched_count,
            total_to_match=task.total_to_match,
            total_lines=task.total_lines,
            error_message=task.error_message,
            created_at=task.created_at,
            completed_at=task.completed_at,
            aggregated_file_path=task.aggregated_file_path,
            spin_matched_file_path=task.spin_matched_file_path,
        )
