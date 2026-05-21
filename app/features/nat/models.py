from __future__ import annotations

from datetime import datetime
from enum import IntEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class NATTaskStatus(IntEnum):
    CANCELLED = -20
    QUEUED = -1
    LAUNCHED = 10
    IN_PROGRESS = 20
    COMPLETED = 30


class NatBatch(Base, TimestampMixin):
    __tablename__ = 'nat_batches'

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        index=True,
        comment='Primary key (UUID v4, generated automatically)',
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
        comment='Number of rows in CSV file (excluding header). Max: 500',
    )

    created_by: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        comment='User ID (UUID format) who initiated this batch',
    )

    tasks: Mapped[list[NatTask]] = relationship(
        'NatTask',
        back_populates='batch',
        cascade='all, delete-orphan',
        lazy='selectin',
        comment='Individual NAT tasks derived from this batch file',
    )

    __table_args__ = (
        CheckConstraint(
            'row_count >= 1 AND row_count <= 500',
            name='ck_nat_batches_row_count_range',
            comment='Row count must be between 1 and 500 inclusive',
        ),
        {
            'comment': 'NAT batch files containing multiple processing requests',
        },
    )

    def __repr__(self) -> str:
        return (
            f'NatBatch('
            f'id={self.id}, '
            f'file_name={self.file_name}, '
            f'row_count={self.row_count}, '
            f'tasks_count={len(self.tasks)})'
        )

    @property
    def completed_count(self) -> int:
        return sum(1 for task in self.tasks if task.status == NATTaskStatus.COMPLETED)

    @property
    def failed_count(self) -> int:
        return sum(
            1
            for task in self.tasks
            if task.status == NATTaskStatus.CANCELLED
            or (
                task.status
                not in (
                    NATTaskStatus.COMPLETED,
                    NATTaskStatus.IN_PROGRESS,
                    NATTaskStatus.LAUNCHED,
                    NATTaskStatus.QUEUED,
                )
            )
        )

    @property
    def progress_percentage(self) -> float:
        if not self.tasks:
            return 0.0
        return (self.completed_count / len(self.tasks)) * 100

    @property
    def is_fully_processed(self) -> bool:
        if not self.tasks:
            return False
        terminal_states = (
            NATTaskStatus.COMPLETED,
            NATTaskStatus.CANCELLED,
        )
        return all(task.status in terminal_states for task in self.tasks)


class NatTask(Base, TimestampMixin):
    __tablename__ = 'nat_tasks'

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        index=True,
        comment='Internal primary key (UUID v4, generated automatically)',
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

    nat_request_uuid: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment='NAT API request UUID (returned in response, for reference)',
    )

    status: Mapped[NATTaskStatus] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        default=NATTaskStatus.QUEUED,
        server_default=text(str(NATTaskStatus.QUEUED.value)),
        comment='Processing status code from NAT API',
    )

    progress: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment='Progress percentage (0-100) from NAT API',
    )

    datetime_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment='Start of selection interval (YYYY-MM-DD HH:MM:SS)',
    )

    datetime_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment='End of selection interval (YYYY-MM-DD HH:MM:SS)',
    )

    src_xlated: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment='External (translated) source IPv4',
    )

    src_port_xlated: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment='External source port',
    )

    src: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment='Internal source IPv4 (before NAT)',
    )

    src_port: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment='Internal source port',
    )

    dst: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment='Destination IPv4',
    )

    dst_port: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment='Destination port',
    )

    regions: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment='Region numbers comma-separated (see NAT region справочник)',
    )

    nat_user: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment='User login/email for NAT API authentication',
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

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment='When NAT started processing this request',
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment='When NAT finished processing this request',
    )

    duration: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment='Processing duration (as returned by NAT, e.g., "00:03:32")',
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment='Error description if task failed',
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment='Number of retry attempts',
    )

    batch: Mapped[NatBatch] = relationship(
        'NatBatch',
        back_populates='tasks',
    )

    __table_args__ = (
        CheckConstraint(
            'status IN (-20, -1, 10, 20, 30)',
            name='ck_nat_tasks_status_valid',
            comment='Status must be a valid NAT status code',
        ),
        CheckConstraint(
            'progress >= 0 AND progress <= 100',
            name='ck_nat_tasks_progress_range',
            comment='Progress must be between 0 and 100',
        ),
        CheckConstraint(
            'retry_count >= 0',
            name='ck_nat_tasks_retry_count_non_negative',
            comment='Retry count cannot be negative',
        ),
        CheckConstraint(
            'src_port_xlated >= 0 AND src_port_xlated <= 65535',
            name='ck_nat_tasks_src_port_xlated_range',
            comment='Source port (xlated) must be valid port number',
        ),
        CheckConstraint(
            'src_port >= 0 AND src_port <= 65535',
            name='ck_nat_tasks_src_port_range',
            comment='Source port must be valid port number',
        ),
        CheckConstraint(
            'dst_port >= 0 AND dst_port <= 65535',
            name='ck_nat_tasks_dst_port_range',
            comment='Destination port must be valid port number',
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
            f'status={self.status.name}, '
            f'batch_id={self.batch_id})'
        )

    @property
    def is_terminal_state(self) -> bool:
        return self.status in (
            NATTaskStatus.COMPLETED,
            NATTaskStatus.CANCELLED,
        )

    @property
    def is_error_state(self) -> bool:
        if self.status == NATTaskStatus.CANCELLED:
            return True
        valid_states = (
            NATTaskStatus.QUEUED,
            NATTaskStatus.LAUNCHED,
            NATTaskStatus.IN_PROGRESS,
            NATTaskStatus.COMPLETED,
        )
        return self.status not in valid_states

    @property
    def is_completed(self) -> bool:
        return self.status == NATTaskStatus.COMPLETED

    @property
    def can_retry(self) -> bool:
        return self.is_error_state and self.retry_count < 3

    def to_nat_api_payload(self) -> dict[str, str | None]:
        return {
            'ACTION': 'send',
            'user': self.nat_user,
            'datetime_from': self.datetime_from.strftime('%Y-%m-%d %H:%M:%S')
            if self.datetime_from
            else None,
            'datetime_to': self.datetime_to.strftime('%Y-%m-%d %H:%M:%S')
            if self.datetime_to
            else None,
            'srcXlated': self.src_xlated,
            'srcPortXlated': str(self.src_port_xlated)
            if self.src_port_xlated is not None
            else None,
            'src': self.src,
            'srcPort': str(self.src_port) if self.src_port is not None else None,
            'dst': self.dst,
            'dstPort': str(self.dst_port) if self.dst_port is not None else None,
            'region': self.regions,
        }
