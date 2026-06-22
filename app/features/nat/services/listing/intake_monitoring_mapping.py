from app.features.email.constants import EmailReplyStatus
from app.features.nat.constants import (
    IntakeStatus,
    ValidationErrorCode,
    is_file_level_intake_rejection,
)
from app.features.nat.repository_records import (
    NatIntakeListRecord,
    NatIntakeMonitoringListRecord,
)
from app.features.nat.schemas.intake_monitoring import (
    IntakeFileRowStats,
    IntakeNatTaskStats,
    NatIntakeMonitoringListItem,
)
from app.features.nat.services.listing.intake_mapping import to_intake_list_item


def to_monitoring_list_item(
    record: NatIntakeMonitoringListRecord,
) -> NatIntakeMonitoringListItem:
    base = to_intake_list_item(
        _to_list_record(record),
    )
    return NatIntakeMonitoringListItem(
        **base.model_dump(),
        rows=_build_row_stats(record),
        tasks=_build_task_stats(record),
        email_reply_status=_parse_reply_status(record.email_reply_status),
    )


def _to_list_record(record: NatIntakeMonitoringListRecord) -> NatIntakeListRecord:
    return NatIntakeListRecord(
        intake=record.intake,
        batch_id=record.batch_id,
        processing_paused=record.processing_paused,
    )


def _build_row_stats(
    record: NatIntakeMonitoringListRecord,
) -> IntakeFileRowStats | None:
    if record.batch_id is not None:
        assert record.batch_row_count is not None
        total = record.batch_row_count
        rejected = record.rejected_row_count
        return IntakeFileRowStats(
            total=total,
            rejected=rejected,
            passed=total - rejected,
        )

    intake = record.intake
    if (
        intake.status == IntakeStatus.REJECTED.value
        and intake.error_code == ValidationErrorCode.NO_VALID_ROWS.value
    ):
        rejected = record.rejected_row_count
        return IntakeFileRowStats(
            total=rejected,
            rejected=rejected,
            passed=0,
        )

    if intake.status == IntakeStatus.REJECTED.value and is_file_level_intake_rejection(
        intake.error_code
    ):
        return None

    return None


def _build_task_stats(
    record: NatIntakeMonitoringListRecord,
) -> IntakeNatTaskStats | None:
    if record.tasks_total is None:
        return None

    total = record.tasks_total
    pending_dispatch = record.tasks_pending_dispatch or 0
    in_progress = record.tasks_in_progress or 0
    completed = record.tasks_completed or 0
    failed = total - pending_dispatch - in_progress - completed
    return IntakeNatTaskStats(
        total=total,
        pending_dispatch=pending_dispatch,
        in_progress=in_progress,
        completed=completed,
        failed=failed,
    )


def _parse_reply_status(value: str | None) -> EmailReplyStatus | None:
    if value is None:
        return None
    return EmailReplyStatus(value)
