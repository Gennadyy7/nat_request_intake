from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.repositories.sqlalchemy import SQLAlchemyRepository
from app.features.nat.domain.deduplication_key import DeduplicationKey
from app.features.nat.models import NatBatch, NatDedupKey, NatTask
from app.features.nat.services.deduplication.deduplication_key import build_key_hash

logger = get_logger(__name__)


class NatBatchRepository(SQLAlchemyRepository[NatBatch, UUID]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=NatBatch, session=session)


class NatTaskRepository(SQLAlchemyRepository[NatTask, UUID]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=NatTask, session=session)


class NatDedupKeyRepository(SQLAlchemyRepository[NatDedupKey, UUID]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=NatDedupKey, session=session)

    async def register_if_absent(self, key: DeduplicationKey) -> bool:
        now = datetime.now(UTC)
        window_start = now - timedelta(minutes=settings.NAT_IDEMPOTENCY_WINDOW_MINUTES)
        key_hash = build_key_hash(key)

        await self._session.execute(
            delete(NatDedupKey).where(NatDedupKey.created_at < window_start)
        )

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
        inserted_id = result.scalar_one_or_none()
        registered = inserted_id is not None
        logger.debug(
            'Deduplication key registration: key_hash={} registered={}',
            key_hash,
            registered,
        )
        return registered
