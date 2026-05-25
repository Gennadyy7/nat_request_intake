from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.repositories.sqlalchemy import SQLAlchemyRepository
from app.features.nat.models import NatBatch, NatTask

logger = get_logger(__name__)


class NatBatchRepository(SQLAlchemyRepository[NatBatch, UUID]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=NatBatch, session=session)


class NatTaskRepository(SQLAlchemyRepository[NatTask, int]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=NatTask, session=session)
