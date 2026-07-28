from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import exists, func, literal, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repositories.sqlalchemy import SQLAlchemyRepository
from app.features.assomi.constants import AssomiTaskStatus
from app.features.assomi.models import AssomiTask
from app.features.nat.constants import NatResultProcessingStatus
from app.features.nat.models import NatResultProcessingTask


class AssomiTaskRepository(SQLAlchemyRepository[AssomiTask, UUID]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(model=AssomiTask, session=session)

    async def ensure_pending_for_completed_aggregation_tasks(self) -> int:
        has_spin_matched_path = text(
            """
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(aggregation_tasks.output_files) AS elem
                WHERE COALESCE(elem->>'spin_matched_path', '') <> ''
            )
            """
        )
        already_enqueued = exists(
            select(AssomiTask.id).where(
                AssomiTask.aggregation_task_id == NatResultProcessingTask.id,
            )
        )
        statement = (
            insert(AssomiTask)
            .from_select(
                [
                    'id',
                    'aggregation_task_id',
                    'nat_batch_id',
                    'status',
                ],
                select(
                    func.gen_random_uuid(),
                    NatResultProcessingTask.id,
                    NatResultProcessingTask.nat_batch_id,
                    literal(AssomiTaskStatus.PENDING.value),
                ).where(
                    NatResultProcessingTask.status
                    == NatResultProcessingStatus.COMPLETED.value,
                    has_spin_matched_path,
                    ~already_enqueued,
                ),
            )
            .on_conflict_do_nothing(index_elements=['aggregation_task_id'])
        )
        result = await self._session.execute(statement)
        rowcount = getattr(result, 'rowcount', None)
        return int(rowcount or 0)

    async def claim_for_processing(self, limit: int | None) -> Sequence[AssomiTask]:
        statement = (
            select(AssomiTask)
            .where(AssomiTask.status == AssomiTaskStatus.PENDING.value)
            .order_by(AssomiTask.created_at.asc())
            .with_for_update(skip_locked=True)
        )
        if limit is not None:
            statement = statement.limit(limit)
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def mark_completed(
        self,
        task_id: UUID,
        *,
        output_path: str,
        found_count: int,
        missing_count: int,
    ) -> None:
        now = datetime.now(UTC)
        await self._session.execute(
            update(AssomiTask)
            .where(AssomiTask.id == task_id)
            .values(
                status=AssomiTaskStatus.COMPLETED.value,
                output_path=output_path,
                error_message=None,
                found_count=found_count,
                missing_count=missing_count,
                completed_at=now,
                updated_at=now,
            )
        )

    async def mark_failed(self, task_id: UUID, *, error_message: str) -> None:
        now = datetime.now(UTC)
        await self._session.execute(
            update(AssomiTask)
            .where(AssomiTask.id == task_id)
            .values(
                status=AssomiTaskStatus.FAILED.value,
                error_message=error_message,
                completed_at=now,
                updated_at=now,
            )
        )
