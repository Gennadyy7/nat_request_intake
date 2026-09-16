from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.core.unit_of_work.sqlalchemy import SQLAlchemyUnitOfWork
from assomi_worker.app.core.database import db_manager


@asynccontextmanager
async def unit_of_work() -> AsyncGenerator[UnitOfWorkProtocol, None]:
    async with SQLAlchemyUnitOfWork(db_manager.session_factory) as uow:
        yield uow
