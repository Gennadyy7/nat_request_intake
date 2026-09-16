from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.features.assomi.constants import AssomiTaskStatus
from app.features.nat.constants import IntakeSource


class AssomiTaskListItem(BaseModel):
    id: UUID
    aggregation_task_id: UUID
    batch_id: UUID
    intake_number: int = Field(ge=1)
    status: AssomiTaskStatus
    found_count: int | None = None
    missing_count: int | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class AssomiTaskDetail(AssomiTaskListItem):
    pass


class ManualAssomiEnrichResponse(BaseModel):
    intake_id: UUID
    intake_number: int = Field(ge=1)
    batch_id: UUID
    result_processing_id: UUID
    assomi_task_id: UUID
    source: Literal[IntakeSource.MANUAL_ASSOMI] = IntakeSource.MANUAL_ASSOMI
    status: Literal['accepted_for_assomi_enrichment'] = 'accepted_for_assomi_enrichment'
    file_name: str
