from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.features.nat.constants import (
    DeduplicationErrorCode,
    InputColumnName,
    IntakeStatus,
    NatRegionCode,
    ValidationErrorCode,
)


class FileErrorResponse(BaseModel):
    error_code: ValidationErrorCode


class RowErrorResponse(BaseModel):
    row_number: int = Field(ge=1)
    error_code: ValidationErrorCode | DeduplicationErrorCode
    column: InputColumnName | None = None


class ValidatedRowResponse(BaseModel):
    row_number: int = Field(ge=1)
    date_from: datetime
    date_to: datetime
    internal_ip: str | None
    external_ip: str | None
    resource_ip: str | None
    region: NatRegionCode | None


class IntakeResponse(BaseModel):
    status: IntakeStatus
    file_name: str
    sender_email: EmailStr
    total_data_rows: int = Field(ge=0)
    valid_rows: int = Field(ge=0)
    rejected_rows: int = Field(ge=0)
    file_errors: list[FileErrorResponse]
    row_errors: list[RowErrorResponse]
    validated_rows: list[ValidatedRowResponse]
