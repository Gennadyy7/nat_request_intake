from datetime import datetime

from pydantic import BaseModel, Field

from app.features.assomi.constants import AssomiTaskStatus
from app.features.email.constants import EmailReplyStatus
from app.features.nat.constants import NatResultProcessingStatus
from app.features.nat.schemas.intake_list import NatIntakeListItem


class IntakeFileRowStats(BaseModel):
    total: int = Field(ge=0)
    rejected: int = Field(ge=0)
    passed: int = Field(ge=0)


class IntakeNatTaskStats(BaseModel):
    total: int = Field(ge=0)
    pending_dispatch: int = Field(ge=0)
    in_progress: int = Field(ge=0)
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)


class IntakeResultProcessingStats(BaseModel):
    status: NatResultProcessingStatus
    matched_count: int | None = None
    total_to_match: int | None = None
    total_lines: int = Field(ge=0)
    error_message: str | None = None
    completed_at: datetime | None = None


class IntakeAssomiStats(BaseModel):
    status: AssomiTaskStatus
    found_count: int | None = None
    missing_count: int | None = None
    error_message: str | None = None
    completed_at: datetime | None = None


class NatIntakeMonitoringListItem(NatIntakeListItem):
    rows: IntakeFileRowStats | None = None
    tasks: IntakeNatTaskStats | None = None
    email_reply_status: EmailReplyStatus | None = None
    result_processing: IntakeResultProcessingStats | None = None
    assomi: IntakeAssomiStats | None = None
