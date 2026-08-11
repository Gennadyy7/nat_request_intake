from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from app.features.assomi.constants import AssomiTaskStatus
from app.features.assomi.models import AssomiTask
from app.features.nat.constants import (
    RESULT_SHEET_AGGREGATION,
    RESULT_SHEET_APPLICATION,
    RESULT_SHEET_ASSOMI,
    RESULT_SHEET_SPIN,
    IntakeSource,
    IntakeStatus,
)
from app.features.nat.messages import get_message
from app.features.nat.models import NatBatch, NatIntake, NatResultProcessingTask
from app.features.nat.services.persistence.file_storage import FileStorageService


class SheetKind(StrEnum):
    REJECTION_METADATA = 'rejection_metadata'
    APPLICATION = 'application'
    AGGREGATION = 'aggregation'
    SPIN = 'spin'
    ASSOMI = 'assomi'


@dataclass(frozen=True, slots=True)
class SheetSpec:
    title: str
    kind: SheetKind
    paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class ResultFileStorages:
    nat_upload: FileStorageService
    spin: FileStorageService
    assomi: FileStorageService


def build_sheet_plan(
    *,
    intake: NatIntake,
    batch: NatBatch | None,
    assomi_task: AssomiTask | None,
    aggregation_task: NatResultProcessingTask | None,
    storages: ResultFileStorages,
    merge_stage_files: bool,
) -> list[SheetSpec]:
    if intake.status == IntakeStatus.REJECTED.value and batch is None:
        return [
            SheetSpec(
                title=RESULT_SHEET_APPLICATION,
                kind=SheetKind.REJECTION_METADATA,
                paths=(),
            )
        ]

    specs: list[SheetSpec] = []
    source = IntakeSource(intake.source)

    if source == IntakeSource.NAT and batch is not None:
        application_path = _resolve_readable_path(
            batch.file_name,
            storage=storages.nat_upload,
        )
        if application_path is not None:
            specs.append(
                SheetSpec(
                    title=RESULT_SHEET_APPLICATION,
                    kind=SheetKind.APPLICATION,
                    paths=(application_path,),
                )
            )

    if aggregation_task is not None:
        aggregated_paths = _collect_readable_paths(
            aggregation_task.output_files,
            path_key='aggregated_path',
            storage=storages.spin,
        )
        specs.extend(
            _stage_specs(
                base_title=RESULT_SHEET_AGGREGATION,
                kind=SheetKind.AGGREGATION,
                paths=aggregated_paths,
                merge_stage_files=merge_stage_files,
            )
        )

        spin_paths = _collect_readable_paths(
            aggregation_task.output_files,
            path_key='spin_matched_path',
            storage=storages.spin,
        )
        specs.extend(
            _stage_specs(
                base_title=RESULT_SHEET_SPIN,
                kind=SheetKind.SPIN,
                paths=spin_paths,
                merge_stage_files=merge_stage_files,
            )
        )

    if (
        assomi_task is not None
        and assomi_task.status == AssomiTaskStatus.COMPLETED.value
        and assomi_task.output_path
    ):
        assomi_paths = _collect_readable_paths(
            [{'index': 1, 'path': assomi_task.output_path}],
            path_key='path',
            storage=storages.assomi,
        )
        specs.extend(
            _stage_specs(
                base_title=RESULT_SHEET_ASSOMI,
                kind=SheetKind.ASSOMI,
                paths=assomi_paths,
                merge_stage_files=merge_stage_files,
            )
        )

    return specs


def build_rejection_metadata_rows(*, intake: NatIntake) -> list[list[str]]:
    error_code = intake.error_code or ''
    message = get_message(error_code) if error_code else ''
    return [
        ['Поле', 'Значение'],
        ['Номер заявки', str(intake.number)],
        ['Идентификатор заявки', str(intake.id)],
        ['Файл', intake.file_name],
        ['Код ошибки', error_code],
        ['Сообщение', message],
    ]


def build_download_filename(*, intake_number: int) -> str:
    return f'intake_{intake_number}_results.xlsx'


def _stage_specs(
    *,
    base_title: str,
    kind: SheetKind,
    paths: list[tuple[int, Path]],
    merge_stage_files: bool,
) -> list[SheetSpec]:
    if not paths:
        return []
    if merge_stage_files:
        return [
            SheetSpec(
                title=base_title,
                kind=kind,
                paths=tuple(path for _, path in paths),
            )
        ]

    return [
        SheetSpec(
            title=f'{base_title}_{index}',
            kind=kind,
            paths=(path,),
        )
        for index, path in paths
    ]


def _collect_readable_paths(
    output_files: list[dict[str, object]],
    *,
    path_key: str,
    storage: FileStorageService,
) -> list[tuple[int, Path]]:
    collected: list[tuple[int, Path]] = []
    for output_file in output_files:
        raw_index = output_file.get('index')
        raw_path = output_file.get(path_key)
        if not isinstance(raw_index, int) or not isinstance(raw_path, str):
            continue
        if not raw_path.strip():
            continue
        resolved = _resolve_readable_path(raw_path, storage=storage)
        if resolved is not None:
            collected.append((raw_index, resolved))
    collected.sort(key=lambda item: item[0])
    return collected


def _resolve_readable_path(
    storage_path: str,
    *,
    storage: FileStorageService,
) -> Path | None:
    safe_path = storage.resolve_safe_path(storage_path)
    if safe_path is None or not storage.is_readable_file(safe_path):
        return None
    return safe_path
