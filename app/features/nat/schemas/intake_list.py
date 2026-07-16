from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.features.nat.constants import (
    InputColumnName,
    IntakeSource,
    IntakeStatus,
    RowErrorCode,
    ValidationErrorCode,
)
from app.features.nat.schemas.pagination import PaginationMeta


class NatIntakeListItem(BaseModel):
    id: UUID
    number: int = Field(ge=1)
    sender_email: EmailStr
    file_name: str
    status: IntakeStatus
    source: IntakeSource
    code: ValidationErrorCode | None = None
    message: str | None = None
    batch_id: UUID | None = None
    processing_paused: bool | None = None
    created_at: datetime


class NatIntakeDetail(BaseModel):
    id: UUID
    number: int = Field(ge=1)
    sender_email: EmailStr
    file_name: str
    status: IntakeStatus
    source: IntakeSource
    code: ValidationErrorCode | None = None
    message: str | None = None
    batch_id: UUID | None = None
    processing_paused: bool | None = None
    created_at: datetime


class NatIntakeRowErrorItem(BaseModel):
    row_number: int = Field(ge=1)
    code: RowErrorCode
    column: InputColumnName | None = None
    message: str | None = None


class NatIntakeRowErrorListResponse(BaseModel):
    data: list[NatIntakeRowErrorItem]
    meta: PaginationMeta
