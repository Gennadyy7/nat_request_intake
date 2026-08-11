from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.assomi.models import AssomiTask
from app.features.nat.domain.pipeline_outcome import is_pipeline_terminal
from app.features.nat.models import NatBatch, NatResultProcessingTask, NatTask
from app.features.nat.services.persistence.file_storage import FileStorageService
from app.features.nat.services.results.builder import build_intake_results_xlsx_path
from app.features.nat.services.results.sheet_plan import (
    ResultFileStorages,
    build_download_filename,
)

IntakeResultsResolveStatus = Literal['ok', 'intake_not_found', 'not_ready']


@dataclass(frozen=True, slots=True)
class IntakeResultsFileDescriptor:
    path: Path
    download_filename: str
    cleanup_path: Path


@dataclass(frozen=True, slots=True)
class IntakeResultsResolveResult:
    status: IntakeResultsResolveStatus
    descriptor: IntakeResultsFileDescriptor | None = None


class IntakeResultsService:
    def __init__(
        self,
        *,
        uow: UnitOfWorkProtocol,
        nat_upload_storage: FileStorageService,
        spin_storage: FileStorageService,
        assomi_storage: FileStorageService,
        merge_stage_files: bool,
    ) -> None:
        self._uow = uow
        self._storages = ResultFileStorages(
            nat_upload=nat_upload_storage,
            spin=spin_storage,
            assomi=assomi_storage,
        )
        self._merge_stage_files = merge_stage_files

    async def resolve_download(self, intake_id: UUID) -> IntakeResultsResolveResult:
        intake = await self._uow.nat_intakes.get_by_id(intake_id)
        if intake is None:
            return IntakeResultsResolveResult(status='intake_not_found')

        batch = await self._uow.nat_batches.get_by_intake_id(intake_id)
        assomi_task, aggregation_task, nat_tasks = await self._load_pipeline_context(
            batch
        )

        if not is_pipeline_terminal(
            intake_status=intake.status,
            intake_source=intake.source,
            batch=batch,
            assomi_task=assomi_task,
            aggregation_task=aggregation_task,
            nat_tasks=nat_tasks,
        ):
            return IntakeResultsResolveResult(status='not_ready')

        xlsx_path = await build_intake_results_xlsx_path(
            intake=intake,
            batch=batch,
            assomi_task=assomi_task,
            aggregation_task=aggregation_task,
            storages=self._storages,
            merge_stage_files=self._merge_stage_files,
        )
        return IntakeResultsResolveResult(
            status='ok',
            descriptor=IntakeResultsFileDescriptor(
                path=xlsx_path,
                download_filename=build_download_filename(
                    intake_number=int(intake.number)
                ),
                cleanup_path=xlsx_path,
            ),
        )

    async def _load_pipeline_context(
        self,
        batch: NatBatch | None,
    ) -> tuple[
        AssomiTask | None,
        NatResultProcessingTask | None,
        Sequence[NatTask],
    ]:
        if batch is None:
            return None, None, []

        assomi_task = await self._uow.assomi_tasks.get_by_nat_batch_id(batch.id)
        aggregation_task = await self._uow.nat_result_processing_tasks.get_by_batch_id(
            batch.id
        )
        nat_tasks = list(await self._uow.nat_tasks.list_by_batch_id(batch.id))
        return assomi_task, aggregation_task, nat_tasks
