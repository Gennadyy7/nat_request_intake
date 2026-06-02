from dataclasses import dataclass
from datetime import datetime

from app.features.email.constants import EmailProcessingStatus


@dataclass(frozen=True, slots=True)
class EmailMessageFilters:
    sender_email: str | None = None
    processing_status: EmailProcessingStatus | None = None
    received_at_from: datetime | None = None
    received_at_to: datetime | None = None
