from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.features.email.constants import EmailProcessingStatus, EmailReplyStatus


def normalize_email(value: str) -> str:
    return value.strip().lower()


class EmailSenderCreate(BaseModel):
    email: EmailStr
    name: str | None = Field(default=None, max_length=100)
    contact: str | None = Field(default=None, max_length=200)
    is_active: bool = True

    @field_validator('email', mode='before')
    @classmethod
    def validate_email(cls, value: object) -> str:
        if not isinstance(value, str):
            raise TypeError('email must be a string')
        return normalize_email(value)


class EmailSenderUpdate(BaseModel):
    email: EmailStr | None = None
    name: str | None = Field(default=None, max_length=100)
    contact: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None

    @field_validator('email', mode='before')
    @classmethod
    def validate_email(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError('email must be a string')
        return normalize_email(value)


class EmailSenderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    name: str | None
    contact: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class EmailMessageCreate(BaseModel):
    message_id: str = Field(min_length=1, max_length=1000)
    sender_email: EmailStr
    subject: str | None = Field(default=None, max_length=1000)
    body: str | None = None
    received_at: datetime
    processing_status: EmailProcessingStatus
    nat_intake_id: UUID | None = None
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str | None = None

    @field_validator('sender_email', mode='before')
    @classmethod
    def validate_sender_email(cls, value: object) -> str:
        if not isinstance(value, str):
            raise TypeError('sender_email must be a string')
        return normalize_email(value)


class EmailMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    message_id: str
    sender_email: EmailStr
    subject: str | None
    body: str | None
    received_at: datetime
    processing_status: EmailProcessingStatus
    nat_intake_id: UUID | None
    error_code: str | None
    error_message: str | None
    reply_status: EmailReplyStatus | None
    created_at: datetime
    updated_at: datetime


class EmailMessageListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    message_id: str
    sender_email: EmailStr
    subject: str | None
    received_at: datetime
    processing_status: EmailProcessingStatus
    nat_intake_id: UUID | None
    reply_status: EmailReplyStatus | None
    created_at: datetime
