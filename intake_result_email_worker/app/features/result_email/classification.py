from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.features.assomi.constants import AssomiTaskStatus
from app.features.nat.constants import (
    NON_TERMINAL_NAT_STATUSES,
    IntakeSource,
    NatResultProcessingStatus,
    NatTaskStatus,
)
from intake_result_email_worker.app.features.result_email.messages import (
    AGGREGATION_NO_SPIN_REASON,
    NAT_ALL_FAILED_FALLBACK,
    STAGE_LABEL_AGGREGATION_SPIN,
    STAGE_LABEL_ASSOMI,
    STAGE_LABEL_NAT,
)
from intake_result_email_worker.app.features.result_email.types import (
    ResultEmailKind,
    ResultEmailStage,
)


class AssomiTaskLike(Protocol):
    status: str
    error_message: str | None
    output_path: str | None
    found_count: int | None
    missing_count: int | None


class AggregationTaskLike(Protocol):
    status: str
    error_message: str | None
    output_files: list[dict[str, object]]


class NatTaskLike(Protocol):
    status: int | None
    error_message: str | None


class IntakeLike(Protocol):
    id: UUID
    number: int
    sender_email: str
    file_name: str
    source: str


@dataclass(frozen=True, slots=True)
class ResultEmailClassification:
    kind: ResultEmailKind
    stage: ResultEmailStage | None = None
    reason: str | None = None
    found_count: int | None = None
    missing_count: int | None = None
    output_path: str | None = None


@dataclass(frozen=True, slots=True)
class ResultEmailContext:
    intake_id: UUID
    intake_number: int
    sender_email: str
    file_name: str
    batch_id: UUID
    source: str
    original_subject: str | None
    original_message_id: str | None


def classify_pipeline_outcome(
    *,
    source: str,
    assomi_task: AssomiTaskLike | None,
    aggregation_task: AggregationTaskLike | None,
    nat_tasks: Sequence[NatTaskLike],
) -> ResultEmailClassification | None:
    if (
        assomi_task is not None
        and assomi_task.status == AssomiTaskStatus.COMPLETED.value
    ):
        return ResultEmailClassification(
            kind='success',
            found_count=assomi_task.found_count,
            missing_count=assomi_task.missing_count,
            output_path=assomi_task.output_path,
        )
    if assomi_task is not None and assomi_task.status == AssomiTaskStatus.FAILED.value:
        return ResultEmailClassification(
            kind='failure',
            stage='assomi',
            reason=_non_empty_or_fallback(
                assomi_task.error_message,
                fallback='Ошибка обогащения ASSOMI',
            ),
        )
    if (
        aggregation_task is not None
        and aggregation_task.status == NatResultProcessingStatus.FAILED.value
    ):
        return ResultEmailClassification(
            kind='failure',
            stage='aggregation_spin',
            reason=_non_empty_or_fallback(
                aggregation_task.error_message,
                fallback='Ошибка агрегации / SPIN',
            ),
        )
    if (
        aggregation_task is not None
        and aggregation_task.status == NatResultProcessingStatus.COMPLETED.value
        and not _has_spin_matched_path(aggregation_task.output_files)
        and assomi_task is None
    ):
        return ResultEmailClassification(
            kind='failure',
            stage='aggregation_spin',
            reason=AGGREGATION_NO_SPIN_REASON,
        )
    if source == IntakeSource.NAT.value and _is_nat_all_failed(nat_tasks):
        return ResultEmailClassification(
            kind='failure',
            stage='nat',
            reason=_first_nat_error_message(nat_tasks),
        )
    return None


def build_context(
    *,
    intake: IntakeLike,
    batch_id: UUID,
    original_subject: str | None,
    original_message_id: str | None,
) -> ResultEmailContext:
    return ResultEmailContext(
        intake_id=intake.id,
        intake_number=int(intake.number),
        sender_email=intake.sender_email,
        file_name=intake.file_name,
        batch_id=batch_id,
        source=intake.source,
        original_subject=original_subject,
        original_message_id=original_message_id,
    )


def stage_label(stage: ResultEmailStage) -> str:
    match stage:
        case 'nat':
            return STAGE_LABEL_NAT
        case 'aggregation_spin':
            return STAGE_LABEL_AGGREGATION_SPIN
        case 'assomi':
            return STAGE_LABEL_ASSOMI


def _has_spin_matched_path(output_files: list[dict[str, object]]) -> bool:
    for item in output_files:
        raw_path = item.get('spin_matched_path')
        if isinstance(raw_path, str) and raw_path.strip():
            return True
    return False


def _is_nat_task_non_terminal(task: NatTaskLike) -> bool:
    if task.status is None and task.error_message is None:
        return True
    if task.status is None:
        return False
    return task.status in NON_TERMINAL_NAT_STATUSES


def _is_nat_all_failed(nat_tasks: Sequence[NatTaskLike]) -> bool:
    if not nat_tasks:
        return False
    if any(_is_nat_task_non_terminal(task) for task in nat_tasks):
        return False
    return not any(task.status == NatTaskStatus.COMPLETED for task in nat_tasks)


def _first_nat_error_message(nat_tasks: Sequence[NatTaskLike]) -> str:
    for task in nat_tasks:
        if task.error_message and task.error_message.strip():
            return task.error_message.strip()
    return NAT_ALL_FAILED_FALLBACK


def _non_empty_or_fallback(value: str | None, *, fallback: str) -> str:
    if value is not None and value.strip():
        return value.strip()
    return fallback
