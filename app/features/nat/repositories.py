from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, case, delete, func, insert, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement, Label

from app.core.config import settings
from app.core.logging import get_logger
from app.core.repositories.sqlalchemy import SQLAlchemyRepository
from app.features.assomi.constants import AssomiTaskStatus
from app.features.assomi.models import AssomiTask
from app.features.email.models import EmailMessage
from app.features.nat.constants import (
    NON_TERMINAL_NAT_STATUSES,
    IntakeSource,
    NatResultProcessingStatus,
    NatTaskStatus,
)
from app.features.nat.domain.deduplication_key import DeduplicationKey
from app.features.nat.domain.transformed_row import TransformedRow
from app.features.nat.models import (
    GLOBAL_PROCESSING_SINGLETON_ID,
    NatBatch,
    NatDedupKey,
    NatGlobalProcessing,
    NatIntake,
    NatIntakeRowError,
    NatResultProcessingTask,
    NatTask,
)
from app.features.nat.query_params import (
    NatBatchFilters,
    NatIntakeFilters,
    NatIntakeMonitoringFilters,
    NatResultProcessingFilters,
    NatTaskFilters,
    SortOrder,
    SortParams,
)
from app.features.nat.repository_query import (
    batch_sort_column,
    build_assomi_filter_clauses,
    build_batch_filter_clauses,
    build_intake_filter_clauses,
    build_result_processing_filter_clauses,
    build_result_processing_list_filter_clauses,
    build_task_filter_clauses,
    global_processing_not_paused,
    intake_list_requires_batch_join,
    intake_sort_column,
    monitoring_requires_assomi_join,
    monitoring_requires_result_processing_join,
    order_by_sort_column,
    result_processing_list_requires_intake_join,
    result_processing_sort_column,
    row_error_sort_expression,
    task_list_requires_intake_join,
    task_sort_column,
)
from app.features.nat.repository_records import (
    NatBatchDetailRecord,
    NatBatchListRecord,
    NatIntakeListRecord,
    NatIntakeMonitoringListRecord,
    NatResultProcessingListRecord,
    NatTaskListRecord,
)
from app.features.nat.services.deduplication.deduplication_key import build_key_hash

logger = get_logger(__name__)

# Column order for COPY - computed once at import time from the mapper.
# If NatTask gains a new column, add the corresponding value to the tuple
# in create_many_from_rows to keep positions aligned.
_NAT_TASK_COPY_COLUMNS: list[str] = [
    attr.key for attr in NatTask.__mapper__.column_attrs
]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _rejected_row_count_subquery() -> Label[int]:
    return (
        select(func.count(func.distinct(NatIntakeRowError.row_number)))
        .where(NatIntakeRowError.intake_id == NatIntake.id)
        .correlate(NatIntake)
        .scalar_subquery()
        .label('rejected_row_count')
    )


def _nullable_batch_task_count_subquery(
    *,
    extra_condition: ColumnElement[bool] | None,
    label: str,
) -> Label[int | None]:
    where_clauses: list[ColumnElement[bool]] = [NatTask.batch_id == NatBatch.id]
    if extra_condition is not None:
        where_clauses.append(extra_condition)
    count_subquery = (
        select(func.count(NatTask.id))
        .where(*where_clauses)
        .correlate(NatBatch)
        .scalar_subquery()
    )
    return case(
        (NatBatch.id.is_not(None), count_subquery),
        else_=None,
    ).label(label)


class NatIntakeRepository(SQLAlchemyRepository[NatIntake, UUID]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=NatIntake, session=session)

    async def count_filtered(self, filters: NatIntakeFilters) -> int:
        clauses = build_intake_filter_clauses(filters)
        statement = select(func.count()).select_from(NatIntake)
        if intake_list_requires_batch_join(filters):
            statement = statement.outerjoin(
                NatBatch,
                NatBatch.intake_id == NatIntake.id,
            )
        if clauses:
            statement = statement.where(*clauses)
        result = await self._session.execute(statement)
        return int(result.scalar_one())

    async def list_filtered(
        self,
        filters: NatIntakeFilters,
        sort: SortParams,
        limit: int,
        offset: int,
    ) -> Sequence[NatIntakeListRecord]:
        clauses = build_intake_filter_clauses(filters)
        statement = (
            select(
                NatIntake,
                NatBatch.id,
                NatBatch.processing_paused,
                NatBatch.single_stage_only,
            )
            .outerjoin(NatBatch, NatBatch.intake_id == NatIntake.id)
            .order_by(order_by_sort_column(intake_sort_column(sort), sort.sort_order))
            .limit(limit)
            .offset(offset)
        )
        if clauses:
            statement = statement.where(*clauses)
        result = await self._session.execute(statement)
        return [
            NatIntakeListRecord(
                intake=intake,
                batch_id=batch_id,
                processing_paused=processing_paused,
                single_stage_only=single_stage_only,
            )
            for intake, batch_id, processing_paused, single_stage_only in result.all()
        ]

    async def count_monitoring_filtered(
        self,
        filters: NatIntakeMonitoringFilters,
    ) -> int:
        clauses = build_intake_filter_clauses(filters)
        result_processing_clauses = build_result_processing_filter_clauses(filters)
        assomi_clauses = build_assomi_filter_clauses(filters)
        all_clauses = clauses + result_processing_clauses + assomi_clauses
        statement = (
            select(func.count())
            .select_from(NatIntake)
            .outerjoin(NatBatch, NatBatch.intake_id == NatIntake.id)
        )
        if monitoring_requires_result_processing_join(filters):
            statement = statement.outerjoin(
                NatResultProcessingTask,
                NatResultProcessingTask.nat_batch_id == NatBatch.id,
            )
        if monitoring_requires_assomi_join(filters):
            statement = statement.outerjoin(
                AssomiTask,
                AssomiTask.nat_batch_id == NatBatch.id,
            )
        if all_clauses:
            statement = statement.where(*all_clauses)
        result = await self._session.execute(statement)
        return int(result.scalar_one())

    async def list_monitoring_filtered(
        self,
        filters: NatIntakeMonitoringFilters,
        sort: SortParams,
        limit: int,
        offset: int,
    ) -> Sequence[NatIntakeMonitoringListRecord]:
        clauses = build_intake_filter_clauses(filters)
        result_processing_clauses = build_result_processing_filter_clauses(filters)
        assomi_clauses = build_assomi_filter_clauses(filters)
        all_clauses = clauses + result_processing_clauses + assomi_clauses
        rejected_row_count = _rejected_row_count_subquery()
        tasks_total = _nullable_batch_task_count_subquery(
            extra_condition=None,
            label='tasks_total',
        )
        tasks_pending_dispatch = _nullable_batch_task_count_subquery(
            extra_condition=and_(
                NatTask.status.is_(None),
                NatTask.error_message.is_(None),
            ),
            label='tasks_pending_dispatch',
        )
        tasks_in_progress = _nullable_batch_task_count_subquery(
            extra_condition=NatTask.status.in_(NON_TERMINAL_NAT_STATUSES),
            label='tasks_in_progress',
        )
        tasks_completed = _nullable_batch_task_count_subquery(
            extra_condition=NatTask.status == NatTaskStatus.COMPLETED,
            label='tasks_completed',
        )
        statement = (
            select(
                NatIntake,
                NatBatch.id,
                NatBatch.processing_paused,
                NatBatch.single_stage_only,
                NatBatch.row_count,
                NatBatch.result_emailed_at,
                rejected_row_count,
                EmailMessage.reply_status,
                tasks_total,
                tasks_pending_dispatch,
                tasks_in_progress,
                tasks_completed,
                NatResultProcessingTask.status,
                NatResultProcessingTask.matched_count,
                NatResultProcessingTask.total_to_match,
                NatResultProcessingTask.total_lines,
                NatResultProcessingTask.error_message,
                NatResultProcessingTask.completed_at,
                AssomiTask.status,
                AssomiTask.found_count,
                AssomiTask.missing_count,
                AssomiTask.error_message,
                AssomiTask.completed_at,
            )
            .outerjoin(NatBatch, NatBatch.intake_id == NatIntake.id)
            .outerjoin(
                NatResultProcessingTask,
                NatResultProcessingTask.nat_batch_id == NatBatch.id,
            )
            .outerjoin(
                AssomiTask,
                AssomiTask.nat_batch_id == NatBatch.id,
            )
            .outerjoin(EmailMessage, EmailMessage.nat_intake_id == NatIntake.id)
            .order_by(order_by_sort_column(intake_sort_column(sort), sort.sort_order))
            .limit(limit)
            .offset(offset)
        )
        if all_clauses:
            statement = statement.where(*all_clauses)
        result = await self._session.execute(statement)
        return [
            NatIntakeMonitoringListRecord(
                intake=intake,
                batch_id=batch_id,
                processing_paused=processing_paused,
                single_stage_only=single_stage_only,
                batch_row_count=batch_row_count,
                result_emailed_at=result_emailed_at,
                rejected_row_count=int(rejected_row_count_value),
                email_reply_status=email_reply_status,
                tasks_total=_optional_int(tasks_total_value),
                tasks_pending_dispatch=_optional_int(tasks_pending_dispatch_value),
                tasks_in_progress=_optional_int(tasks_in_progress_value),
                tasks_completed=_optional_int(tasks_completed_value),
                result_processing_status=result_processing_status,
                result_processing_matched_count=_optional_int(
                    result_processing_matched_count,
                ),
                result_processing_total_to_match=_optional_int(
                    result_processing_total_to_match,
                ),
                result_processing_total_lines=_optional_int(
                    result_processing_total_lines,
                ),
                result_processing_error_message=result_processing_error_message,
                result_processing_completed_at=result_processing_completed_at,
                assomi_status=assomi_status,
                assomi_found_count=_optional_int(assomi_found_count),
                assomi_missing_count=_optional_int(assomi_missing_count),
                assomi_error_message=assomi_error_message,
                assomi_completed_at=assomi_completed_at,
            )
            for (
                intake,
                batch_id,
                processing_paused,
                single_stage_only,
                batch_row_count,
                result_emailed_at,
                rejected_row_count_value,
                email_reply_status,
                tasks_total_value,
                tasks_pending_dispatch_value,
                tasks_in_progress_value,
                tasks_completed_value,
                result_processing_status,
                result_processing_matched_count,
                result_processing_total_to_match,
                result_processing_total_lines,
                result_processing_error_message,
                result_processing_completed_at,
                assomi_status,
                assomi_found_count,
                assomi_missing_count,
                assomi_error_message,
                assomi_completed_at,
            ) in result.all()
        ]

    async def get_list_record_by_id(
        self,
        intake_id: UUID,
    ) -> NatIntakeListRecord | None:
        statement = (
            select(
                NatIntake,
                NatBatch.id,
                NatBatch.processing_paused,
                NatBatch.single_stage_only,
            )
            .outerjoin(NatBatch, NatBatch.intake_id == NatIntake.id)
            .where(NatIntake.id == intake_id)
        )
        result = await self._session.execute(statement)
        row = result.one_or_none()
        if row is None:
            return None
        intake, batch_id, processing_paused, single_stage_only = row
        return NatIntakeListRecord(
            intake=intake,
            batch_id=batch_id,
            processing_paused=processing_paused,
            single_stage_only=single_stage_only,
        )


def _optional_int(value: int | None) -> int | None:
    if value is None:
        return None
    return int(value)


class NatIntakeRowErrorRepository(SQLAlchemyRepository[NatIntakeRowError, UUID]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=NatIntakeRowError, session=session)

    async def create_many(self, entities: Sequence[NatIntakeRowError]) -> None:
        session_id = hex(id(self._session))
        if not entities:
            logger.debug(
                f'[{self._model.__name__}] Skipping create_many: no entities provided '
                f'[Session ID: {session_id}]'
            )
            return
        col_keys = [attr.key for attr in NatIntakeRowError.__mapper__.column_attrs]
        logger.debug(
            f'[{self._model.__name__}] Bulk-inserting {len(entities)} entities via Core INSERT '
            f'[Session ID: {session_id}]'
        )
        await self._session.execute(
            insert(NatIntakeRowError),
            [{key: getattr(entity, key) for key in col_keys} for entity in entities],
        )
        logger.debug(
            f'[{self._model.__name__}] {len(entities)} entities bulk-inserted successfully '
            f'[Session ID: {session_id}]'
        )

    async def count_by_intake_id(self, intake_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(NatIntakeRowError)
            .where(NatIntakeRowError.intake_id == intake_id)
        )
        result = await self._session.execute(statement)
        return int(result.scalar_one())

    async def list_by_intake_id(
        self,
        intake_id: UUID,
        *,
        limit: int,
        offset: int,
        sort_order: SortOrder = 'asc',
    ) -> Sequence[NatIntakeRowError]:
        statement = (
            select(NatIntakeRowError)
            .where(NatIntakeRowError.intake_id == intake_id)
            .order_by(row_error_sort_expression(sort_order))
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())


class NatBatchRepository(SQLAlchemyRepository[NatBatch, UUID]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=NatBatch, session=session)

    def _tasks_count_subquery(self) -> Label[int]:
        return (
            select(func.count(NatTask.id))
            .where(NatTask.batch_id == NatBatch.id)
            .correlate(NatBatch)
            .scalar_subquery()
            .label('tasks_count')
        )

    async def count_filtered(self, filters: NatBatchFilters) -> int:
        clauses = build_batch_filter_clauses(filters)
        statement = (
            select(func.count())
            .select_from(NatBatch)
            .join(NatIntake, NatBatch.intake_id == NatIntake.id)
        )
        if clauses:
            statement = statement.where(*clauses)
        result = await self._session.execute(statement)
        return int(result.scalar_one())

    async def list_filtered(
        self,
        filters: NatBatchFilters,
        sort: SortParams,
        limit: int,
        offset: int,
    ) -> Sequence[NatBatchListRecord]:
        clauses = build_batch_filter_clauses(filters)
        tasks_count = self._tasks_count_subquery()
        statement = (
            select(
                NatBatch,
                NatIntake.sender_email,
                NatIntake.file_name,
                NatIntake.number,
                tasks_count,
            )
            .join(NatIntake, NatBatch.intake_id == NatIntake.id)
            .order_by(order_by_sort_column(batch_sort_column(sort), sort.sort_order))
            .limit(limit)
            .offset(offset)
        )
        if clauses:
            statement = statement.where(*clauses)
        result = await self._session.execute(statement)
        return [
            NatBatchListRecord(
                batch=batch,
                sender_email=sender_email,
                original_file_name=original_file_name,
                intake_number=int(intake_number),
                tasks_count=int(tasks_count_value),
            )
            for (
                batch,
                sender_email,
                original_file_name,
                intake_number,
                tasks_count_value,
            ) in result.all()
        ]

    async def get_detail_by_id(self, batch_id: UUID) -> NatBatchDetailRecord | None:
        tasks_count = self._tasks_count_subquery()
        statement = (
            select(
                NatBatch,
                NatIntake.sender_email,
                NatIntake.file_name,
                NatIntake.number,
                tasks_count,
            )
            .join(NatIntake, NatBatch.intake_id == NatIntake.id)
            .where(NatBatch.id == batch_id)
        )
        result = await self._session.execute(statement)
        row = result.one_or_none()
        if row is None:
            return None
        batch, sender_email, original_file_name, intake_number, tasks_count_value = row
        return NatBatchDetailRecord(
            batch=batch,
            sender_email=sender_email,
            original_file_name=original_file_name,
            intake_number=int(intake_number),
            tasks_count=int(tasks_count_value),
        )

    async def claim_for_notification(self, limit: int | None) -> Sequence[NatBatch]:
        pending_dispatch = and_(
            NatTask.status.is_(None),
            NatTask.error_message.is_(None),
        )
        in_flight = NatTask.status.in_(NON_TERMINAL_NAT_STATUSES)
        has_completed = (
            select(NatTask.id)
            .where(
                NatTask.batch_id == NatBatch.id,
                NatTask.status == NatTaskStatus.COMPLETED,
            )
            .correlate(NatBatch)
            .exists()
        )
        has_non_terminal = (
            select(NatTask.id)
            .where(
                NatTask.batch_id == NatBatch.id,
                or_(pending_dispatch, in_flight),
            )
            .correlate(NatBatch)
            .exists()
        )
        statement = (
            select(NatBatch)
            .join(NatIntake, NatBatch.intake_id == NatIntake.id)
            .where(
                NatBatch.notified_at.is_(None),
                NatBatch.processing_paused.is_(False),
                global_processing_not_paused(),
                NatIntake.source == IntakeSource.NAT.value,
                has_completed,
                ~has_non_terminal,
            )
            .order_by(NatBatch.created_at.asc())
            .with_for_update(skip_locked=True)
        )
        if limit is not None:
            statement = statement.limit(limit)
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def claim_for_result_email(
        self,
        limit: int | None,
        *,
        respect_processing_pause: bool,
    ) -> Sequence[NatBatch]:
        pending_dispatch = and_(
            NatTask.status.is_(None),
            NatTask.error_message.is_(None),
        )
        in_flight = NatTask.status.in_(NON_TERMINAL_NAT_STATUSES)
        has_completed_nat = (
            select(NatTask.id)
            .where(
                NatTask.batch_id == NatBatch.id,
                NatTask.status == NatTaskStatus.COMPLETED,
            )
            .correlate(NatBatch)
            .exists()
        )
        has_non_terminal_nat = (
            select(NatTask.id)
            .where(
                NatTask.batch_id == NatBatch.id,
                or_(pending_dispatch, in_flight),
            )
            .correlate(NatBatch)
            .exists()
        )
        has_any_nat_task = (
            select(NatTask.id)
            .where(NatTask.batch_id == NatBatch.id)
            .correlate(NatBatch)
            .exists()
        )
        has_assomi_task = (
            select(AssomiTask.id)
            .where(AssomiTask.nat_batch_id == NatBatch.id)
            .correlate(NatBatch)
            .exists()
        )
        assomi_terminal = (
            select(AssomiTask.id)
            .where(
                AssomiTask.nat_batch_id == NatBatch.id,
                AssomiTask.status.in_(
                    (
                        AssomiTaskStatus.COMPLETED.value,
                        AssomiTaskStatus.FAILED.value,
                    )
                ),
            )
            .correlate(NatBatch)
            .exists()
        )
        aggregation_failed = (
            select(NatResultProcessingTask.id)
            .where(
                NatResultProcessingTask.nat_batch_id == NatBatch.id,
                NatResultProcessingTask.status
                == NatResultProcessingStatus.FAILED.value,
            )
            .correlate(NatBatch)
            .exists()
        )
        has_no_spin_matched_path = text(
            """
            NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(aggregation_tasks.output_files) AS elem
                WHERE COALESCE(elem->>'spin_matched_path', '') <> ''
            )
            """
        )
        aggregation_completed_without_spin = (
            select(NatResultProcessingTask.id)
            .where(
                NatResultProcessingTask.nat_batch_id == NatBatch.id,
                NatResultProcessingTask.status
                == NatResultProcessingStatus.COMPLETED.value,
                has_no_spin_matched_path,
            )
            .correlate(NatBatch)
            .exists()
        )
        nat_all_failed = and_(
            NatIntake.source == IntakeSource.NAT.value,
            has_any_nat_task,
            ~has_completed_nat,
            ~has_non_terminal_nat,
        )
        ready_for_result_email = or_(
            assomi_terminal,
            aggregation_failed,
            and_(aggregation_completed_without_spin, ~has_assomi_task),
            nat_all_failed,
        )
        conditions = [
            NatBatch.result_emailed_at.is_(None),
            NatBatch.single_stage_only.is_(False),
            ready_for_result_email,
        ]
        if respect_processing_pause:
            conditions.append(NatBatch.processing_paused.is_(False))
            conditions.append(global_processing_not_paused())
        statement = (
            select(NatBatch)
            .join(NatIntake, NatBatch.intake_id == NatIntake.id)
            .where(*conditions)
            .order_by(NatBatch.created_at.asc())
            .with_for_update(skip_locked=True)
        )
        if limit is not None:
            statement = statement.limit(limit)
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def claim_for_single_stage_nat_stop_on_all_failed(
        self,
        limit: int | None,
    ) -> Sequence[NatBatch]:
        pending_dispatch = and_(
            NatTask.status.is_(None),
            NatTask.error_message.is_(None),
        )
        in_flight = NatTask.status.in_(NON_TERMINAL_NAT_STATUSES)
        has_completed = (
            select(NatTask.id)
            .where(
                NatTask.batch_id == NatBatch.id,
                NatTask.status == NatTaskStatus.COMPLETED,
            )
            .correlate(NatBatch)
            .exists()
        )
        has_non_terminal = (
            select(NatTask.id)
            .where(
                NatTask.batch_id == NatBatch.id,
                or_(pending_dispatch, in_flight),
            )
            .correlate(NatBatch)
            .exists()
        )
        has_any_nat_task = (
            select(NatTask.id)
            .where(NatTask.batch_id == NatBatch.id)
            .correlate(NatBatch)
            .exists()
        )
        statement = (
            select(NatBatch)
            .join(NatIntake, NatBatch.intake_id == NatIntake.id)
            .where(
                NatBatch.single_stage_only.is_(True),
                NatBatch.processing_paused.is_(False),
                global_processing_not_paused(),
                NatIntake.source == IntakeSource.NAT.value,
                has_any_nat_task,
                ~has_completed,
                ~has_non_terminal,
            )
            .order_by(NatBatch.created_at.asc())
            .with_for_update(skip_locked=True)
        )
        if limit is not None:
            statement = statement.limit(limit)
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def mark_notified(self, batch_id: UUID) -> None:
        await self._session.execute(
            update(NatBatch)
            .where(NatBatch.id == batch_id)
            .values(
                notified_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

    async def mark_result_emailed(self, batch_id: UUID) -> None:
        now = datetime.now(UTC)
        await self._session.execute(
            update(NatBatch)
            .where(NatBatch.id == batch_id)
            .values(
                result_emailed_at=now,
                updated_at=now,
            )
        )

    async def get_by_intake_id(self, intake_id: UUID) -> NatBatch | None:
        statement = select(NatBatch).where(NatBatch.intake_id == intake_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def set_processing_paused(self, batch_id: UUID, *, paused: bool) -> None:
        values: dict[str, bool | datetime] = {
            'processing_paused': paused,
            'updated_at': datetime.now(UTC),
        }
        if not paused:
            values['single_stage_only'] = False
        await self._session.execute(
            update(NatBatch).where(NatBatch.id == batch_id).values(**values)
        )


class NatGlobalProcessingRepository(SQLAlchemyRepository[NatGlobalProcessing, int]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(model=NatGlobalProcessing, session=session)

    async def _ensure_singleton(self) -> None:
        statement = (
            pg_insert(NatGlobalProcessing)
            .values(
                id=GLOBAL_PROCESSING_SINGLETON_ID,
                processing_paused=False,
            )
            .on_conflict_do_nothing(index_elements=['id'])
        )
        await self._session.execute(statement)

    async def get_singleton(self) -> NatGlobalProcessing | None:
        statement = select(NatGlobalProcessing).where(
            NatGlobalProcessing.id == GLOBAL_PROCESSING_SINGLETON_ID,
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def is_processing_paused(self) -> bool:
        statement = select(NatGlobalProcessing.processing_paused).where(
            NatGlobalProcessing.id == GLOBAL_PROCESSING_SINGLETON_ID,
        )
        result = await self._session.execute(statement)
        value = result.scalar_one_or_none()
        return bool(value)

    async def set_processing_paused(self, *, paused: bool) -> None:
        await self._ensure_singleton()
        await self._session.execute(
            update(NatGlobalProcessing)
            .where(NatGlobalProcessing.id == GLOBAL_PROCESSING_SINGLETON_ID)
            .values(
                processing_paused=paused,
                updated_at=datetime.now(UTC),
            )
        )


class NatTaskRepository(SQLAlchemyRepository[NatTask, UUID]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=NatTask, session=session)

    async def create_many_from_rows(
        self,
        rows: Sequence[TransformedRow],
        batch_id: UUID,
    ) -> None:
        session_id = hex(id(self._session))
        if not rows:
            logger.debug(
                f'[{self._model.__name__}] Skipping create_many_from_rows: no rows provided '
                f'[Session ID: {session_id}]'
            )
            return

        now = datetime.now(UTC)
        records = [
            (
                uuid4(),  # id
                batch_id,  # batch_id
                None,  # nat_request_id
                _as_utc(row.datetime_from),  # datetime_from
                _as_utc(row.datetime_to),  # datetime_to
                row.src_xlated,  # src_xlated
                row.src_port_xlated,  # src_port_xlated
                row.src,  # src
                row.src_port,  # src_port
                row.dst,  # dst
                row.dst_port,  # dst_port
                row.region,  # region
                None,  # status
                None,  # progress
                None,  # count_of_lines
                None,  # nat_file_id
                None,  # file_url
                None,  # file_size
                None,  # file_type
                None,  # error_message
                now,  # created_at
                now,  # updated_at
            )
            for row in rows
        ]
        logger.debug(
            f'[{self._model.__name__}] Bulk-inserting {len(records)} rows via COPY protocol '
            f'[Session ID: {session_id}]'
        )
        conn = await self._session.connection()
        raw = await conn.get_raw_connection()
        asyncpg_conn = raw.driver_connection
        assert asyncpg_conn is not None
        await asyncpg_conn.copy_records_to_table(
            'nat_tasks',
            records=records,
            columns=_NAT_TASK_COPY_COLUMNS,
        )
        logger.debug(
            f'[{self._model.__name__}] {len(records)} rows bulk-inserted successfully via COPY '
            f'[Session ID: {session_id}]'
        )

    async def list_by_batch_id(self, batch_id: UUID) -> Sequence[NatTask]:
        statement = (
            select(NatTask)
            .where(NatTask.batch_id == batch_id)
            .order_by(NatTask.created_at.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def count_filtered(self, filters: NatTaskFilters) -> int:
        clauses = build_task_filter_clauses(filters)
        statement = select(func.count()).select_from(NatTask)
        if task_list_requires_intake_join(filters):
            statement = statement.join(NatBatch, NatTask.batch_id == NatBatch.id).join(
                NatIntake,
                NatBatch.intake_id == NatIntake.id,
            )
        if clauses:
            statement = statement.where(*clauses)
        result = await self._session.execute(statement)
        return int(result.scalar_one())

    async def list_filtered(
        self,
        filters: NatTaskFilters,
        sort: SortParams,
        limit: int,
        offset: int,
    ) -> Sequence[NatTaskListRecord]:
        clauses = build_task_filter_clauses(filters)
        statement = (
            select(NatTask, NatIntake.number)
            .join(NatBatch, NatTask.batch_id == NatBatch.id)
            .join(NatIntake, NatBatch.intake_id == NatIntake.id)
            .order_by(order_by_sort_column(task_sort_column(sort), sort.sort_order))
            .limit(limit)
            .offset(offset)
        )
        if clauses:
            statement = statement.where(*clauses)
        result = await self._session.execute(statement)
        return [
            NatTaskListRecord(task=task, intake_number=int(intake_number))
            for task, intake_number in result.all()
        ]

    async def get_list_record_by_id(
        self,
        task_id: UUID,
    ) -> NatTaskListRecord | None:
        statement = (
            select(NatTask, NatIntake.number)
            .join(NatBatch, NatTask.batch_id == NatBatch.id)
            .join(NatIntake, NatBatch.intake_id == NatIntake.id)
            .where(NatTask.id == task_id)
        )
        result = await self._session.execute(statement)
        row = result.one_or_none()
        if row is None:
            return None
        task, intake_number = row
        return NatTaskListRecord(task=task, intake_number=int(intake_number))

    async def claim_for_dispatch(self, limit: int | None) -> Sequence[NatTask]:
        statement = (
            select(NatTask)
            .join(NatBatch, NatTask.batch_id == NatBatch.id)
            .join(NatIntake, NatBatch.intake_id == NatIntake.id)
            .where(
                NatTask.status.is_(None),
                NatTask.error_message.is_(None),
                NatBatch.processing_paused.is_(False),
                global_processing_not_paused(),
                NatIntake.source == IntakeSource.NAT.value,
            )
            .order_by(NatTask.created_at.asc())
            .with_for_update(skip_locked=True)
        )
        if limit is not None:
            statement = statement.limit(limit)
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def claim_for_poll(self, limit: int | None) -> Sequence[NatTask]:
        statement = (
            select(NatTask)
            .join(NatBatch, NatTask.batch_id == NatBatch.id)
            .join(NatIntake, NatBatch.intake_id == NatIntake.id)
            .where(
                NatTask.status.in_(NON_TERMINAL_NAT_STATUSES),
                NatIntake.source == IntakeSource.NAT.value,
            )
            .order_by(NatTask.created_at.asc())
            .with_for_update(skip_locked=True)
        )
        if limit is not None:
            statement = statement.limit(limit)
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def update_after_send(
        self,
        task_id: UUID,
        *,
        nat_request_id: int,
        status: int,
    ) -> None:
        await self._session.execute(
            update(NatTask)
            .where(NatTask.id == task_id)
            .values(
                nat_request_id=nat_request_id,
                status=status,
                updated_at=datetime.now(UTC),
            )
        )

    async def mark_send_permanent_failure(
        self,
        task_id: UUID,
        *,
        error_message: str,
    ) -> None:
        await self._session.execute(
            update(NatTask)
            .where(NatTask.id == task_id)
            .values(
                error_message=error_message,
                updated_at=datetime.now(UTC),
            )
        )

    async def update_after_poll(
        self,
        task_id: UUID,
        *,
        status: int,
        progress: str | None,
        count_of_lines: str | None,
        nat_file_id: int | None,
        file_url: str | None,
        file_size: str | None,
        file_type: str | None,
    ) -> None:
        await self._session.execute(
            update(NatTask)
            .where(NatTask.id == task_id)
            .values(
                status=status,
                progress=progress,
                count_of_lines=count_of_lines,
                nat_file_id=nat_file_id,
                file_url=file_url,
                file_size=file_size,
                file_type=file_type,
                updated_at=datetime.now(UTC),
            )
        )

    async def mark_poll_permanent_failure(
        self,
        task_id: UUID,
        *,
        error_message: str,
    ) -> None:
        await self._session.execute(
            update(NatTask)
            .where(NatTask.id == task_id)
            .values(
                status=NatTaskStatus.LOCAL_ABANDONED,
                error_message=error_message,
                updated_at=datetime.now(UTC),
            )
        )


class NatDedupKeyRepository(SQLAlchemyRepository[NatDedupKey, UUID]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=NatDedupKey, session=session)

    async def exists_within_window(self, key: DeduplicationKey) -> bool:
        now = datetime.now(UTC)
        window_start = now - timedelta(minutes=settings.NAT_IDEMPOTENCY_WINDOW_MINUTES)
        key_hash = build_key_hash(key)
        result = await self._session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM nat_dedup_keys
                    WHERE key_hash = :key_hash
                      AND created_at >= :window_start
                )
                """
            ),
            {
                'key_hash': key_hash,
                'window_start': window_start,
            },
        )
        return bool(result.scalar_one())

    async def purge_expired(self) -> None:
        now = datetime.now(UTC)
        window_start = now - timedelta(minutes=settings.NAT_IDEMPOTENCY_WINDOW_MINUTES)
        await self._session.execute(
            delete(NatDedupKey).where(NatDedupKey.created_at < window_start)
        )

    async def register_if_absent(self, key: DeduplicationKey) -> bool:
        now = datetime.now(UTC)
        window_start = now - timedelta(minutes=settings.NAT_IDEMPOTENCY_WINDOW_MINUTES)
        key_hash = build_key_hash(key)

        insert_stmt = text(
            """
            INSERT INTO nat_dedup_keys (
                id,
                key_hash,
                date_from,
                date_to,
                internal_ip,
                external_ip,
                resource_ip,
                region,
                created_at,
                updated_at
            )
            SELECT
                :id,
                :key_hash_insert,
                :date_from,
                :date_to,
                :internal_ip,
                :external_ip,
                :resource_ip,
                :region,
                :created_at,
                :updated_at
            WHERE NOT EXISTS (
                SELECT 1
                FROM nat_dedup_keys
                WHERE key_hash = :key_hash_lookup
                  AND created_at >= :window_start
            )
            RETURNING id
            """
        )
        try:
            async with self._session.begin_nested():
                result = await self._session.execute(
                    insert_stmt,
                    {
                        'id': uuid4(),
                        'key_hash_insert': key_hash,
                        'key_hash_lookup': key_hash,
                        'date_from': key.date_from,
                        'date_to': key.date_to,
                        'internal_ip': key.internal_ip,
                        'external_ip': key.external_ip,
                        'resource_ip': key.resource_ip,
                        'region': key.region.value if key.region is not None else None,
                        'created_at': now,
                        'updated_at': now,
                        'window_start': window_start,
                    },
                )
                await self._session.flush()
        except IntegrityError:
            logger.debug(
                'Deduplication key registration conflict: key_hash={}',
                key_hash,
            )
            return False

        inserted_id = result.scalar_one_or_none()
        registered = inserted_id is not None
        logger.debug(
            'Deduplication key registration: key_hash={} registered={}',
            key_hash,
            registered,
        )
        return registered


class NatResultProcessingTaskRepository(
    SQLAlchemyRepository[NatResultProcessingTask, UUID],
):
    def __init__(self, session: AsyncSession):
        super().__init__(model=NatResultProcessingTask, session=session)

    async def get_by_batch_id(self, batch_id: UUID) -> NatResultProcessingTask | None:
        statement = select(NatResultProcessingTask).where(
            NatResultProcessingTask.nat_batch_id == batch_id,
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_list_record_by_id(
        self,
        result_processing_id: UUID,
    ) -> NatResultProcessingListRecord | None:
        statement = (
            select(NatResultProcessingTask, NatIntake.number)
            .join(NatBatch, NatResultProcessingTask.nat_batch_id == NatBatch.id)
            .join(NatIntake, NatBatch.intake_id == NatIntake.id)
            .where(NatResultProcessingTask.id == result_processing_id)
        )
        result = await self._session.execute(statement)
        row = result.one_or_none()
        if row is None:
            return None
        task, intake_number = row
        return NatResultProcessingListRecord(
            task=task,
            intake_number=int(intake_number),
        )

    async def get_list_record_by_batch_id(
        self,
        batch_id: UUID,
    ) -> NatResultProcessingListRecord | None:
        statement = (
            select(NatResultProcessingTask, NatIntake.number)
            .join(NatBatch, NatResultProcessingTask.nat_batch_id == NatBatch.id)
            .join(NatIntake, NatBatch.intake_id == NatIntake.id)
            .where(NatResultProcessingTask.nat_batch_id == batch_id)
        )
        result = await self._session.execute(statement)
        row = result.one_or_none()
        if row is None:
            return None
        task, intake_number = row
        return NatResultProcessingListRecord(
            task=task,
            intake_number=int(intake_number),
        )

    async def count_filtered(self, filters: NatResultProcessingFilters) -> int:
        clauses = build_result_processing_list_filter_clauses(filters)
        statement = select(func.count()).select_from(NatResultProcessingTask)
        if result_processing_list_requires_intake_join(filters):
            statement = statement.join(
                NatBatch,
                NatResultProcessingTask.nat_batch_id == NatBatch.id,
            ).join(
                NatIntake,
                NatBatch.intake_id == NatIntake.id,
            )
        if clauses:
            statement = statement.where(*clauses)
        result = await self._session.execute(statement)
        return int(result.scalar_one())

    async def list_filtered(
        self,
        filters: NatResultProcessingFilters,
        sort: SortParams,
        limit: int,
        offset: int,
    ) -> Sequence[NatResultProcessingListRecord]:
        clauses = build_result_processing_list_filter_clauses(filters)
        statement = (
            select(NatResultProcessingTask, NatIntake.number)
            .join(NatBatch, NatResultProcessingTask.nat_batch_id == NatBatch.id)
            .join(NatIntake, NatBatch.intake_id == NatIntake.id)
            .order_by(
                order_by_sort_column(
                    result_processing_sort_column(sort),
                    sort.sort_order,
                )
            )
            .limit(limit)
            .offset(offset)
        )
        if clauses:
            statement = statement.where(*clauses)
        result = await self._session.execute(statement)
        return [
            NatResultProcessingListRecord(
                task=task,
                intake_number=int(intake_number),
            )
            for task, intake_number in result.all()
        ]
