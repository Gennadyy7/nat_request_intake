from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class NatBatchListItem(BaseModel):
    id: UUID
    intake_id: UUID
    file_name: str
    row_count: int = Field(ge=0)
    tasks_count: int = Field(ge=0)
    sender_email: EmailStr
    created_at: datetime


class NatBatchDetail(BaseModel):
    id: UUID
    intake_id: UUID
    file_name: str
    stored_file_path: str
    row_count: int = Field(ge=0)
    tasks_count: int = Field(ge=0)
    sender_email: EmailStr
    created_at: datetime
