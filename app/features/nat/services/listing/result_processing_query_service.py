import asyncio
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Literal
from uuid import UUID
import zipfile

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.constants import (
    ZIP_DOWNLOAD_MEDIA_TYPE,
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
from app.features.nat.services.persistence.file_storage import FileStorageService

ResultProcessingOutputKind = Literal['aggregated', 'spin_matched']
ResultProcessingFileResolveStatus = Literal[
    'ok',
    'not_found',
    'not_ready',
    'file_not_found',
]


@dataclass(frozen=True, slots=True)
class ResultProcessingGetResult:
    status: ResultProcessingGetStatus
    detail: NatResultProcessingDetail | None = None


@dataclass(frozen=True, slots=True)
class ResultProcessingFileDescriptor:
    path: Path
    download_filename: str
    media_type: str
    cleanup_path: Path | None = None


@dataclass(frozen=True, slots=True)
class ResultProcessingFileResolveResult:
    status: ResultProcessingFileResolveStatus
    descriptor: ResultProcessingFileDescriptor | None = None


class ResultProcessingQueryService:
    def __init__(
        self,
        *,
        uow: UnitOfWorkProtocol,
        file_storage: FileStorageService,
    ) -> None:
        self._uow = uow
        self._file_storage = file_storage

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

    async def resolve_aggregated_file(
        self,
        result_processing_id: UUID,
    ) -> ResultProcessingFileResolveResult:
        return await self._resolve_output_file(
            result_processing_id,
            kind='aggregated',
        )

    async def resolve_spin_matched_file(
        self,
        result_processing_id: UUID,
    ) -> ResultProcessingFileResolveResult:
        return await self._resolve_output_file(
            result_processing_id,
            kind='spin_matched',
        )

    async def _resolve_output_file(
        self,
        result_processing_id: UUID,
        *,
        kind: ResultProcessingOutputKind,
    ) -> ResultProcessingFileResolveResult:
        record = await self._uow.nat_result_processing_tasks.get_list_record_by_id(
            result_processing_id
        )
        if record is None:
            return ResultProcessingFileResolveResult(status='not_found')

        task = record.task
        if task.status != NatResultProcessingStatus.COMPLETED.value:
            return ResultProcessingFileResolveResult(status='not_ready')

        indexed_paths = self._collect_output_paths(task.output_files, kind=kind)
        if not indexed_paths:
            return ResultProcessingFileResolveResult(status='file_not_found')

        resolved_files: list[tuple[int, Path]] = []
        for index, storage_path in indexed_paths:
            safe_path = self._file_storage.resolve_safe_path(storage_path)
            if safe_path is None or not self._file_storage.is_readable_file(safe_path):
                return ResultProcessingFileResolveResult(status='file_not_found')
            resolved_files.append((index, safe_path))

        if len(resolved_files) == 1:
            _, path = resolved_files[0]
            download_filename = path.name
            return ResultProcessingFileResolveResult(
                status='ok',
                descriptor=ResultProcessingFileDescriptor(
                    path=path,
                    download_filename=download_filename,
                    media_type=self._file_storage.resolve_media_type(download_filename),
                ),
            )

        zip_path = await self._build_zip_archive(
            resolved_files,
            result_processing_id=result_processing_id,
            kind=kind,
        )
        return ResultProcessingFileResolveResult(
            status='ok',
            descriptor=ResultProcessingFileDescriptor(
                path=zip_path,
                download_filename=self._zip_download_filename(
                    result_processing_id,
                    kind=kind,
                ),
                media_type=ZIP_DOWNLOAD_MEDIA_TYPE,
                cleanup_path=zip_path,
            ),
        )

    def _collect_output_paths(
        self,
        output_files: list[dict[str, object]],
        *,
        kind: ResultProcessingOutputKind,
    ) -> list[tuple[int, str]]:
        path_key = 'aggregated_path' if kind == 'aggregated' else 'spin_matched_path'
        collected: list[tuple[int, str]] = []
        for output_file in output_files:
            raw_index = output_file.get('index')
            raw_path = output_file.get(path_key)
            if not isinstance(raw_index, int) or not isinstance(raw_path, str):
                continue
            if raw_path == '':
                continue
            collected.append((raw_index, raw_path))
        collected.sort(key=lambda item: item[0])
        return collected

    async def _build_zip_archive(
        self,
        files: list[tuple[int, Path]],
        *,
        result_processing_id: UUID,
        kind: ResultProcessingOutputKind,
    ) -> Path:
        suffix = '_aggregated.zip' if kind == 'aggregated' else '_spin_matched.zip'
        with tempfile.NamedTemporaryFile(
            prefix=f'{result_processing_id}',
            suffix=suffix,
            delete=False,
        ) as handle:
            zip_path = Path(handle.name)

        def _write() -> None:
            used_names: set[str] = set()
            with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                for index, path in files:
                    arcname = path.name
                    if arcname in used_names:
                        arcname = f'{index}_{arcname}'
                    used_names.add(arcname)
                    zf.write(path, arcname=arcname)

        try:
            await asyncio.to_thread(_write)
        except Exception:
            zip_path.unlink(missing_ok=True)
            raise
        return zip_path

    def _zip_download_filename(
        self,
        result_processing_id: UUID,
        *,
        kind: ResultProcessingOutputKind,
    ) -> str:
        if kind == 'aggregated':
            return f'{result_processing_id}_aggregated.zip'
        return f'{result_processing_id}_spin_matched.zip'

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
        return NatResultProcessingDetail(
            **self._to_list_item(record).model_dump(),
        )
