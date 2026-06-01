from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class NatIntake(Base, TimestampMixin):
    __tablename__ = 'nat_intakes'

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        index=True,
        comment='Primary key (UUID v4, generated automatically)',
    )

    sender_email: Mapped[str] = mapped_column(
        String(254),
        nullable=False,
        index=True,
        comment='Email address of the user who submitted the file',
    )

    file_name: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment='Original uploaded file name',
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment='Intake processing status (accepted, partially_accepted, rejected)',
    )

    error_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment='File-level validation error code when the intake is rejected',
    )

    batch: Mapped[NatBatch | None] = relationship(
        'NatBatch',
        back_populates='intake',
        uselist=False,
        cascade='all, delete-orphan',
    )

    row_errors: Mapped[list[NatIntakeRowError]] = relationship(
        'NatIntakeRowError',
        back_populates='intake',
        cascade='all, delete-orphan',
        order_by='NatIntakeRowError.row_number',
    )

    __table_args__ = (
        {
            'comment': 'NAT file intake attempts including rejected and accepted uploads',
        },
    )

    def __repr__(self) -> str:
        return (
            f'NatIntake('
            f'id={self.id}, '
            f'file_name={self.file_name}, '
            f'status={self.status}, '
            f'sender_email={self.sender_email})'
        )


class NatIntakeRowError(Base):
    __tablename__ = 'nat_intake_row_errors'

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        comment='Primary key (UUID v4, generated automatically)',
    )

    intake_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            'nat_intakes.id',
            name='fk_nat_intake_row_errors_intake_id_nat_intakes',
            ondelete='CASCADE',
        ),
        nullable=False,
        index=True,
        comment='Foreign key to parent NatIntake',
    )

    row_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment='1-based row number in the uploaded file',
    )

    error_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment='Row-level error code from validation, deduplication, or transformation',
    )

    column: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment='Input column name related to the error, when applicable',
    )

    intake: Mapped[NatIntake] = relationship(
        'NatIntake',
        back_populates='row_errors',
    )

    __table_args__ = (
        {
            'comment': 'Row-level errors collected during NAT intake processing',
        },
    )

    def __repr__(self) -> str:
        return (
            f'NatIntakeRowError('
            f'id={self.id}, '
            f'intake_id={self.intake_id}, '
            f'row_number={self.row_number}, '
            f'error_code={self.error_code})'
        )


class NatBatch(Base, TimestampMixin):
    __tablename__ = 'nat_batches'

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        index=True,
        comment='Primary key (UUID v4, generated automatically)',
    )

    intake_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            'nat_intakes.id',
            name='fk_nat_batches_intake_id_nat_intakes',
            ondelete='CASCADE',
        ),
        nullable=False,
        unique=True,
        index=True,
        comment='Foreign key to parent NatIntake',
    )

    file_name: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        index=True,
        comment='Path to the uploaded file in backend/uploads/nat/',
    )

    row_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment='Number of rows in file (excluding header)',
    )

    intake: Mapped[NatIntake] = relationship(
        'NatIntake',
        back_populates='batch',
    )

    tasks: Mapped[list[NatTask]] = relationship(
        'NatTask',
        back_populates='batch',
        cascade='all, delete-orphan',
        order_by='NatTask.created_at',
    )

    __table_args__ = (
        {
            'comment': 'NAT batch files containing multiple processing requests',
        },
    )

    def __repr__(self) -> str:
        return (
            f'NatBatch('
            f'id={self.id}, '
            f'intake_id={self.intake_id}, '
            f'file_name={self.file_name}, '
            f'row_count={self.row_count})'
        )


class NatTask(Base, TimestampMixin):
    __tablename__ = 'nat_tasks'

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        index=True,
        comment='Primary key (UUID v4, generated automatically)',
    )

    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            'nat_batches.id',
            name='fk_nat_tasks_batch_id_nat_batches',
            ondelete='CASCADE',
        ),
        nullable=False,
        index=True,
        comment='Foreign key to parent NatBatch',
    )

    nat_request_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment='NAT API request ID (returned after ACTION=send). Used for polling.',
    )

    datetime_from: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment='Start datetime for NAT request (dd.mm.yyyy hh:mm:ss)',
    )

    datetime_to: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment='End datetime for NAT request (dd.mm.yyyy hh:mm:ss)',
    )

    src_xlated: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
        comment='External source IPv4 for NAT request',
    )

    src_port_xlated: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment='External source port for NAT request',
    )

    src: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
        comment='Internal source IPv4 for NAT request',
    )

    src_port: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment='Internal source port for NAT request',
    )

    dst: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
        comment='Destination IPv4 for NAT request',
    )

    dst_port: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment='Destination port for NAT request',
    )

    region: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        comment='Region code for NAT request (1-8 or placeholder)',
    )

    status: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment='Processing status code from NAT API; NULL until assigned',
    )

    progress: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment='Progress percentage as returned by NAT API',
    )

    nat_response_file: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment='Path to the response file from NAT (when status=30)',
    )

    count_of_lines: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment='Number of lines in response (as returned by NAT, e.g., "12 345")',
    )

    file_size: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment='Size of response file (as returned by NAT, e.g., "4.21MB")',
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment='Error description if task failed',
    )

    batch: Mapped[NatBatch] = relationship(
        'NatBatch',
        back_populates='tasks',
    )

    __table_args__ = (
        {
            'comment': 'Individual NAT tasks for each request in a batch file',
        },
    )

    def __repr__(self) -> str:
        return (
            f'NatTask('
            f'id={self.id}, '
            f'nat_request_id={self.nat_request_id}, '
            f'status={self.status}, '
            f'batch_id={self.batch_id})'
        )


class NatDedupKey(Base, TimestampMixin):
    __tablename__ = 'nat_dedup_keys'

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        comment='Primary key (UUID v4, generated automatically)',
    )

    key_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment='SHA-256 hash of the deduplication key fields',
    )

    date_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment='Start datetime from the deduplication key',
    )

    date_to: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment='End datetime from the deduplication key',
    )

    internal_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment='Internal IP from the deduplication key',
    )

    external_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment='External IP from the deduplication key',
    )

    resource_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment='Resource IP from the deduplication key',
    )

    region: Mapped[str | None] = mapped_column(
        String(8),
        nullable=True,
        comment='Region code from the deduplication key',
    )

    __table_args__ = (
        {
            'comment': 'Registered deduplication keys for idempotency window tracking',
        },
    )
