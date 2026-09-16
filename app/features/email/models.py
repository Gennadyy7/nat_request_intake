from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class EmailSender(Base, TimestampMixin):
    __tablename__ = 'email_senders'

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        comment='Primary key (UUID v4, generated automatically)',
    )

    email: Mapped[str] = mapped_column(
        String(254),
        nullable=False,
        unique=True,
        comment='Whitelisted sender address (lowercase)',
    )

    name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment='Display name for the sender',
    )

    contact: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment='Optional contact information',
    )

    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        comment='Whether the sender is included in IMAP monitoring',
    )

    __table_args__ = (
        {
            'comment': 'Whitelisted email senders allowed to submit files via IMAP',
        },
    )

    def __repr__(self) -> str:
        return (
            f'EmailSender(id={self.id}, email={self.email}, is_active={self.is_active})'
        )


class EmailMessage(Base, TimestampMixin):
    __tablename__ = 'email_messages'

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        index=True,
        comment='Primary key (UUID v4, generated automatically)',
    )

    message_id: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        unique=True,
        comment='RFC Message-ID or surrogate id for deduplication',
    )

    sender_email: Mapped[str] = mapped_column(
        String(254),
        nullable=False,
        index=True,
        comment='Normalized sender address from the email From header',
    )

    subject: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment='Decoded email subject',
    )

    body: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment='Plain-text body extracted from the email',
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment='Received timestamp from Date header or processing time',
    )

    processing_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment='Processing outcome: accepted, rejected, or skipped',
    )

    nat_intake_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            'nat_intakes.id',
            name='fk_email_messages_nat_intake_id_nat_intakes',
            ondelete='SET NULL',
        ),
        nullable=True,
        index=True,
        comment='Linked NAT intake after B2B processing (null when skipped)',
    )

    error_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment='Error code from IntakeResponse when status is rejected',
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment='Error message from IntakeResponse when status is rejected',
    )

    reply_status: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        index=True,
        comment=(
            'Outbound reply delivery status: sent, failed, or null if not applicable'
        ),
    )

    __table_args__ = (
        {
            'comment': 'Audit log of emails processed by the IMAP poller',
        },
    )

    def __repr__(self) -> str:
        return (
            f'EmailMessage('
            f'id={self.id}, '
            f'message_id={self.message_id!r}, '
            f'processing_status={self.processing_status})'
        )
