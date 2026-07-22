from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.features.nat.constants import (
    NON_TERMINAL_NAT_STATUSES,
    IntakeSource,
    NatAggregationQueueProcessingType,
    NatAggregationQueueStatus,
)


class NatIntake(Base, TimestampMixin):
    __tablename__ = 'nat_intakes'

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        index=True,
        comment='Primary key (UUID v4, generated automatically)',
    )

    number: Mapped[int] = mapped_column(
        BigInteger,
        Identity(start=1, increment=1),
        nullable=False,
        unique=True,
        index=True,
        comment='Human-readable sequential intake number (DB-generated)',
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

    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=IntakeSource.NAT.value,
        server_default=IntakeSource.NAT.value,
        index=True,
        comment='Intake source (nat or manual_spin)',
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
            f'number={self.number}, '
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

    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment='Timestamp when the external service was notified about batch readiness',
    )

    processing_paused: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text('false'),
        comment=(
            'When true, dispatch and notify workers skip this batch; '
            'poll continues for already sent tasks'
        ),
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

    result_processing_task: Mapped[NatResultProcessingTask | None] = relationship(
        'NatResultProcessingTask',
        back_populates='batch',
        uselist=False,
    )

    __table_args__ = (
        Index(
            'ix_nat_batches_notify_queue',
            'created_at',
            postgresql_where=text('notified_at IS NULL'),
        ),
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
            f'row_count={self.row_count}, '
            f'notified_at={self.notified_at})'
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

    datetime_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment='Start datetime for NAT request',
    )

    datetime_to: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment='End datetime for NAT request',
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

    progress: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment='Progress as returned by NAT API (e.g., "100.00")',
    )

    count_of_lines: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment='Number of lines in response (as returned by NAT, e.g., "12 345")',
    )

    nat_file_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment='File ID from NAT API files[] response',
    )

    file_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment='Download URL from NAT API',
    )

    file_size: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment='File size as returned by NAT API',
    )

    file_type: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment='File type as returned by NAT API',
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
        Index(
            'ix_nat_tasks_dispatch_queue',
            'created_at',
            postgresql_where=text('status IS NULL AND error_message IS NULL'),
        ),
        Index(
            'ix_nat_tasks_poll_queue',
            'created_at',
            postgresql_where=status.in_(tuple(NON_TERMINAL_NAT_STATUSES)),
        ),
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


class NatResultProcessingTask(Base):
    __tablename__ = 'aggregation_tasks'

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        index=True,
        comment='Primary key (UUID v4, generated automatically)',
    )

    nat_batch_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            'nat_batches.id',
            name='fk_aggregation_tasks_nat_batch_id_nat_batches',
            ondelete='CASCADE',
        ),
        nullable=False,
        unique=True,
        index=True,
        comment='Foreign key to parent NatBatch',
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default='pending',
        comment=(
            'Result processing status '
            '(pending, downloading, aggregating, matching_spin, completed, failed)'
        ),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment='Timestamp when result processing was started',
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment='Timestamp when result processing finished',
    )

    output_files: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        comment=(
            'Result files: [{index, aggregated_path, spin_matched_path}, ...]. '
            'Contains one item without split and one item per part after split'
        ),
    )

    total_lines: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text('0'),
        comment='Number of lines processed during aggregation',
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment='Error description when result processing failed',
    )

    matched_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment='Number of records matched with SPIN3',
    )

    total_to_match: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment='Total number of records to match with SPIN3',
    )

    batch: Mapped[NatBatch] = relationship(
        'NatBatch',
        back_populates='result_processing_task',
    )

    __table_args__ = (
        {
            'comment': (
                'External post-processing task for aggregating NAT results and SPIN3 matching'
            ),
        },
    )

    def __repr__(self) -> str:
        return (
            f'NatResultProcessingTask('
            f'id={self.id}, '
            f'nat_batch_id={self.nat_batch_id}, '
            f'status={self.status})'
        )


class NatAggregationQueueEntry(Base, TimestampMixin):
    __tablename__ = 'aggregation_queue'

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        comment='Primary key (UUID v4, generated automatically)',
    )

    nat_batch_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            'nat_batches.id',
            name='fk_aggregation_queue_nat_batch_id_nat_batches',
            ondelete='CASCADE',
        ),
        nullable=False,
        unique=True,
        index=True,
        comment='Foreign key to parent NatBatch',
    )

    processing_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=NatAggregationQueueProcessingType.AGGREGATION.value,
        server_default=NatAggregationQueueProcessingType.AGGREGATION.value,
        comment='Queue processing type (aggregation or spin_match)',
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=NatAggregationQueueStatus.PENDING.value,
        server_default=NatAggregationQueueStatus.PENDING.value,
        comment='Queue entry status (pending, processing, completed, failed)',
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text('0'),
        comment='Number of processing attempts for this queue entry',
    )

    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment='Earliest timestamp when the entry may be claimed again',
    )

    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment='Timestamp when a worker claimed the entry',
    )

    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment='Last heartbeat timestamp from the worker holding the lease',
    )

    worker_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment='Identifier of the worker currently holding the lease',
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment='Last error description for retry or failed status',
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment='Timestamp when queue processing finished',
    )

    __table_args__ = (
        Index(
            'ix_aggregation_queue_pending',
            'next_attempt_at',
            'created_at',
            postgresql_where=text("status = 'pending'"),
        ),
        {
            'comment': (
                'Durable aggregation queue schema owned by intake; '
                'runtime processing belongs to nat_result_aggregator'
            ),
        },
    )

    def __repr__(self) -> str:
        return (
            f'NatAggregationQueueEntry('
            f'id={self.id}, '
            f'nat_batch_id={self.nat_batch_id}, '
            f'status={self.status}, '
            f'processing_type={self.processing_type})'
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
