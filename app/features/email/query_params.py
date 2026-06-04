from dataclasses import dataclass
from datetime import datetime
from typing import Final

from app.features.email.constants import EmailProcessingStatus, EmailReplyStatus

EMAIL_SENDER_SORT_COLUMNS: Final[frozenset[str]] = frozenset(
    {'email', 'created_at', 'updated_at'}
)
EMAIL_MESSAGE_SORT_COLUMNS: Final[frozenset[str]] = frozenset(
    {'received_at', 'created_at', 'updated_at'}
)


@dataclass(frozen=True, slots=True)
class EmailSenderFilters:
    email: str | None = None
    is_active: bool | None = None


@dataclass(frozen=True, slots=True)
class EmailMessageFilters:
    sender_email: str | None = None
    processing_status: EmailProcessingStatus | None = None
    reply_status: EmailReplyStatus | None = None
    reply_status_is_null: bool = False
    received_at_from: datetime | None = None
    received_at_to: datetime | None = None
