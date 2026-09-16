from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.features.nat.constants import (
    InputColumnName,
    IntakeSource,
    IntakeStatus,
    RowErrorCode,
    ValidationErrorCode,
)


class RowErrorResponse(BaseModel):
    row_number: int = Field(ge=1)
    code: RowErrorCode
    column: InputColumnName | None = None
    message: str | None = None


class IntakeResponse(BaseModel):
    intake_id: UUID
    number: int = Field(ge=1)
    batch_id: UUID | None = None
    status: IntakeStatus
    source: IntakeSource = IntakeSource.NAT
    file_name: str
    sender_email: EmailStr
    total_data_rows: int = Field(ge=0)
    valid_rows: int = Field(ge=0)
    rejected_rows: int = Field(ge=0)
    code: ValidationErrorCode | None = None
    message: str | None = None
