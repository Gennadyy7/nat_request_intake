from collections.abc import Sequence
from typing import Protocol

from app.features.assomi.constants import AssomiTaskStatus
from app.features.nat.constants import (
    NON_TERMINAL_NAT_STATUSES,
    IntakeSource,
    IntakeStatus,
    NatResultProcessingStatus,
    NatTaskStatus,
)


class AggregationTaskLike(Protocol):
    status: str
    output_files: list[dict[str, object]]


class NatTaskLike(Protocol):
    status: int | None
    error_message: str | None


class AssomiTaskTerminalLike(Protocol):
    status: str


class BatchTerminalLike(Protocol):
    single_stage_only: bool


def has_spin_matched_path(output_files: list[dict[str, object]]) -> bool:
    for item in output_files:
        raw_path = item.get('spin_matched_path')
        if isinstance(raw_path, str) and raw_path.strip():
            return True
    return False


def is_nat_task_non_terminal(task: NatTaskLike) -> bool:
    if task.status is None and task.error_message is None:
        return True
    if task.status is None:
        return False
    return task.status in NON_TERMINAL_NAT_STATUSES


def is_nat_all_failed(
    *,
    intake_source: str,
    nat_tasks: Sequence[NatTaskLike],
) -> bool:
    if intake_source != IntakeSource.NAT.value:
        return False
    if not nat_tasks:
        return False
    if any(is_nat_task_non_terminal(task) for task in nat_tasks):
        return False
    return not any(task.status == NatTaskStatus.COMPLETED for task in nat_tasks)


def is_pipeline_terminal(
    *,
    intake_status: str,
    intake_source: str,
    batch: BatchTerminalLike | None,
    assomi_task: AssomiTaskTerminalLike | None,
    aggregation_task: AggregationTaskLike | None,
    nat_tasks: Sequence[NatTaskLike],
) -> bool:
    if intake_status == IntakeStatus.REJECTED.value:
        return True
    if batch is None:
        return False
    if batch.single_stage_only:
        return False

    if assomi_task is not None and assomi_task.status in (
        AssomiTaskStatus.COMPLETED.value,
        AssomiTaskStatus.FAILED.value,
    ):
        return True

    if (
        aggregation_task is not None
        and aggregation_task.status == NatResultProcessingStatus.FAILED.value
    ):
        return True

    if (
        aggregation_task is not None
        and aggregation_task.status == NatResultProcessingStatus.COMPLETED.value
        and not has_spin_matched_path(aggregation_task.output_files)
        and assomi_task is None
    ):
        return True

    return is_nat_all_failed(intake_source=intake_source, nat_tasks=nat_tasks)
