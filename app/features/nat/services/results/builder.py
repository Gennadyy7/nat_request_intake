import asyncio
from pathlib import Path

from app.features.assomi.models import AssomiTask
from app.features.nat.models import NatBatch, NatIntake, NatResultProcessingTask
from app.features.nat.services.results.errors import IntakeResultsEmptyError
from app.features.nat.services.results.sheet_plan import (
    ResultFileStorages,
    SheetKind,
    SheetSpec,
    build_rejection_metadata_rows,
    build_sheet_plan,
)
from app.features.nat.services.results.tabular_loader import (
    load_application_rows,
    load_csv_rows,
    merge_csv_parts,
)
from app.features.nat.services.results.xlsx_builder import build_results_xlsx_file


async def build_intake_results_xlsx_path(
    *,
    intake: NatIntake,
    batch: NatBatch | None,
    assomi_task: AssomiTask | None,
    aggregation_task: NatResultProcessingTask | None,
    storages: ResultFileStorages,
    merge_stage_files: bool,
) -> Path:
    sheet_specs = build_sheet_plan(
        intake=intake,
        batch=batch,
        assomi_task=assomi_task,
        aggregation_task=aggregation_task,
        storages=storages,
        merge_stage_files=merge_stage_files,
    )
    if not sheet_specs:
        raise IntakeResultsEmptyError(
            'No readable pipeline artifacts available for intake results workbook'
        )
    resolved_sheets = await asyncio.gather(
        *[
            _resolve_sheet_rows(
                spec=spec,
                intake=intake,
            )
            for spec in sheet_specs
        ]
    )
    return await build_results_xlsx_file(sheets=resolved_sheets)


async def _resolve_sheet_rows(
    *,
    spec: SheetSpec,
    intake: NatIntake,
) -> tuple[str, list[list[str]]]:
    if spec.kind == SheetKind.REJECTION_METADATA:
        return spec.title, build_rejection_metadata_rows(intake=intake)

    if spec.kind == SheetKind.APPLICATION:
        assert len(spec.paths) == 1
        path = spec.paths[0]
        rows = await asyncio.to_thread(
            load_application_rows,
            path,
            original_filename=intake.file_name,
        )
        return spec.title, rows

    if len(spec.paths) == 1:
        path = spec.paths[0]
        rows = await asyncio.to_thread(load_csv_rows, path)
        return spec.title, rows

    rows = await asyncio.to_thread(merge_csv_parts, list(spec.paths))
    return spec.title, rows
