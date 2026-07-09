from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.features.nat.constants import NatResultProcessingStatus


class NatResultProcessingDetail(BaseModel):
    id: UUID
    batch_id: UUID
    status: NatResultProcessingStatus
    matched_count: int | None = None
    total_to_match: int | None = None
    total_lines: int = Field(ge=0)
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    aggregated_file_path: str | None = None
    spin_matched_file_path: str | None = None
