from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.features.nat.constants import (
    InputColumnName,
    IntakeStatus,
    RowErrorCode,
    ValidationErrorCode,
)
from app.features.nat.schemas.pagination import PaginationMeta


class NatIntakeListItem(BaseModel):
    id: UUID
    sender_email: EmailStr
    file_name: str
    status: IntakeStatus
    error_code: ValidationErrorCode | None = None
    message: str | None = None
    batch_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class NatIntakeDetail(BaseModel):
    id: UUID
    sender_email: EmailStr
    file_name: str
    status: IntakeStatus
    error_code: ValidationErrorCode | None = None
    message: str | None = None
    batch_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class NatIntakeRowErrorItem(BaseModel):
    row_number: int = Field(ge=1)
    error_code: RowErrorCode
    column: InputColumnName | None = None
    message: str | None = None


class NatIntakeRowErrorListResponse(BaseModel):
    data: list[NatIntakeRowErrorItem]
    meta: PaginationMeta
