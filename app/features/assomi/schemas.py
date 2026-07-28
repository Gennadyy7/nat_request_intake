from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.features.assomi.constants import AssomiTaskStatus


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
