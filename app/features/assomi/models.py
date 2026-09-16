from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.features.assomi.constants import AssomiTaskStatus


class AssomiTask(Base, TimestampMixin):
    __tablename__ = 'assomi_tasks'

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        index=True,
        comment='Primary key (UUID v4, generated automatically)',
    )

    aggregation_task_id: Mapped[UUID] = mapped_column(
        nullable=False,
        unique=True,
        index=True,
        comment=(
            'Logical reference to aggregation_tasks.id (no DB FK; '
            'SPIN result-processing bounded context)'
        ),
    )

    nat_batch_id: Mapped[UUID] = mapped_column(
        nullable=False,
        index=True,
        comment=(
            'Logical reference to NatBatch.id (no DB FK; copied from aggregation task)'
        ),
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=AssomiTaskStatus.PENDING.value,
        comment='ASSOMI enrichment status (pending, completed, failed)',
    )

    output_path: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        comment='Absolute path to ASSOMI CSV artifact on the shared volume',
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment='Error description when ASSOMI enrichment failed permanently',
    )

    found_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment='Number of unique logins found in ASSOMI response',
    )

    missing_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment='Number of unique logins missing from ASSOMI response',
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment='Timestamp when ASSOMI enrichment finished (completed or failed)',
    )

    __table_args__ = (
        Index(
            'ix_assomi_tasks_pending_created_at',
            'created_at',
            postgresql_where=text("status = 'pending'"),
        ),
        {
            'comment': (
                'ASSOMI enrichment tasks for completed SPIN matching results; '
                'aggregation_task_id / nat_batch_id are logical UUIDs without DB FK'
            ),
        },
    )

    def __repr__(self) -> str:
        return (
            f'AssomiTask('
            f'id={self.id}, '
            f'aggregation_task_id={self.aggregation_task_id}, '
            f'status={self.status})'
        )
