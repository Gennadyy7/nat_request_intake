from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.features.nat.models import (
    NatBatch,
    NatIntake,
    NatResultProcessingTask,
    NatTask,
)


@dataclass(frozen=True, slots=True)
class NatBatchListRecord:
    batch: NatBatch
    sender_email: str
    original_file_name: str
    intake_number: int
    tasks_count: int


@dataclass(frozen=True, slots=True)
class NatBatchDetailRecord:
    batch: NatBatch
    sender_email: str
    original_file_name: str
    intake_number: int
    tasks_count: int


@dataclass(frozen=True, slots=True)
class NatIntakeListRecord:
    intake: NatIntake
    batch_id: UUID | None
    processing_paused: bool | None


@dataclass(frozen=True, slots=True)
class NatTaskListRecord:
    task: NatTask
    intake_number: int


@dataclass(frozen=True, slots=True)
class NatResultProcessingListRecord:
    task: NatResultProcessingTask
    intake_number: int


@dataclass(frozen=True, slots=True)
class NatIntakeMonitoringListRecord:
    intake: NatIntake
    batch_id: UUID | None
    processing_paused: bool | None
    batch_row_count: int | None
    result_emailed_at: datetime | None
    rejected_row_count: int
    email_reply_status: str | None
    tasks_total: int | None
    tasks_pending_dispatch: int | None
    tasks_in_progress: int | None
    tasks_completed: int | None
    result_processing_status: str | None
    result_processing_matched_count: int | None
    result_processing_total_to_match: int | None
    result_processing_total_lines: int | None
    result_processing_error_message: str | None
    result_processing_completed_at: datetime | None
    assomi_status: str | None
    assomi_found_count: int | None
    assomi_missing_count: int | None
    assomi_error_message: str | None
    assomi_completed_at: datetime | None
