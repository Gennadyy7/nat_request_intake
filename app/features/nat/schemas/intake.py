from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.features.nat.constants import (
    InputColumnName,
    IntakeStatus,
    RowErrorCode,
    ValidationErrorCode,
)


class FileErrorResponse(BaseModel):
    error_code: ValidationErrorCode


class RowErrorResponse(BaseModel):
    row_number: int = Field(ge=1)
    error_code: RowErrorCode
    column: InputColumnName | None = None


class TransformedRowResponse(BaseModel):
    row_number: int = Field(ge=1)
    datetime_from: str
    datetime_to: str
    src_xlated: str
    src_port_xlated: int | None = None
    src: str
    src_port: int | None = None
    dst: str
    dst_port: int | None = None
    region: str


class IntakeResponse(BaseModel):
    status: IntakeStatus
    file_name: str
    sender_email: EmailStr
    batch_id: UUID | None = None
    total_data_rows: int = Field(ge=0)
    valid_rows: int = Field(ge=0)
    rejected_rows: int = Field(ge=0)
    file_errors: list[FileErrorResponse]
    row_errors: list[RowErrorResponse]
    transformed_rows: list[TransformedRowResponse]
