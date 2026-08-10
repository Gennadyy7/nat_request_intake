from datetime import datetime

from app.features.assomi.constants import AssomiTaskStatus
from app.features.email.constants import EmailReplyStatus
from app.features.nat.constants import (
    IntakeSource,
    IntakeStatus,
    NatResultProcessingStatus,
    ValidationErrorCode,
    is_file_level_intake_rejection,
)
from app.features.nat.repository_records import (
    NatIntakeListRecord,
    NatIntakeMonitoringListRecord,
)
from app.features.nat.schemas.intake_monitoring import (
    IntakeAssomiStats,
    IntakeFileRowStats,
    IntakeNatTaskStats,
    IntakeResultProcessingStats,
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
        result_email_status=_parse_result_email_status(record.result_emailed_at),
        result_processing=_build_result_processing_stats(record),
        assomi=_build_assomi_stats(record),
    )


def _to_list_record(record: NatIntakeMonitoringListRecord) -> NatIntakeListRecord:
    return NatIntakeListRecord(
        intake=record.intake,
        batch_id=record.batch_id,
        processing_paused=record.processing_paused,
        single_stage_only=record.single_stage_only,
    )


def _is_manual_bypass_source(source: str) -> bool:
    return source in {
        IntakeSource.MANUAL_SPIN.value,
        IntakeSource.MANUAL_ASSOMI.value,
    }


def _build_row_stats(
    record: NatIntakeMonitoringListRecord,
) -> IntakeFileRowStats | None:
    if _is_manual_bypass_source(record.intake.source):
        return None
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
    if _is_manual_bypass_source(record.intake.source):
        return None
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


def _build_result_processing_stats(
    record: NatIntakeMonitoringListRecord,
) -> IntakeResultProcessingStats | None:
    if record.intake.source == IntakeSource.MANUAL_ASSOMI.value:
        return None
    if record.result_processing_status is None:
        return None

    return IntakeResultProcessingStats(
        status=NatResultProcessingStatus(record.result_processing_status),
        matched_count=record.result_processing_matched_count,
        total_to_match=record.result_processing_total_to_match,
        total_lines=record.result_processing_total_lines or 0,
        error_message=record.result_processing_error_message,
        completed_at=record.result_processing_completed_at,
    )


def _build_assomi_stats(
    record: NatIntakeMonitoringListRecord,
) -> IntakeAssomiStats | None:
    if record.assomi_status is None:
        return None

    return IntakeAssomiStats(
        status=AssomiTaskStatus(record.assomi_status),
        found_count=record.assomi_found_count,
        missing_count=record.assomi_missing_count,
        error_message=record.assomi_error_message,
        completed_at=record.assomi_completed_at,
    )


def _parse_reply_status(value: str | None) -> EmailReplyStatus | None:
    if value is None:
        return None
    return EmailReplyStatus(value)


def _parse_result_email_status(
    result_emailed_at: datetime | None,
) -> EmailReplyStatus | None:
    if result_emailed_at is None:
        return None
    return EmailReplyStatus.SENT
