from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.core.unit_of_work.protocol import UnitOfWorkProtocol

logger = get_logger(__name__)


class SQLAlchemyUnitOfWork(UnitOfWorkProtocol):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        # self._items: ItemRepository | None = None
        logger.debug('SQLAlchemyUnitOfWork initialized with session factory')

    # @property
    # def items(self) -> ItemRepository:
    #     if self._items is None:
    #         logger.error(
    #             'Attempted to access repositories outside of context manager block'
    #         )
    #         raise RuntimeError(
    #             'UnitOfWork context is not active. Access attributes inside an "async with" block.'
    #         )
    #     return self._items

    async def __aenter__(self) -> Self:
        logger.debug('Entering UnitOfWork context: opening new database session')
        self._session = self._session_factory()
        assert self._session is not None
        logger.debug(
            f'Database session opened successfully. Session ID: {hex(id(self._session))}'
        )
        # self._items = ItemRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        session_id = hex(id(self._session)) if self._session else 'None'
        logger.debug(f'Exiting UnitOfWork context for Session ID: {session_id}')
        try:
            if exc_type is not None:
                logger.warning(
                    f'Exception detected inside UnitOfWork [Session ID: {session_id}]. '
                    f'Type: {exc_type.__name__}, Value: {exc_val}. Triggering rollback.'
                )
                await self.rollback()
            else:
                logger.debug(
                    f'No exceptions detected. Triggering commit for Session ID: {session_id}'
                )
                await self.commit()
        finally:
            assert self._session is not None
            logger.debug(f'Closing database session. Session ID: {session_id}')
            await self._session.close()
            logger.debug(f'Database session closed. Session ID: {session_id}')

    async def commit(self) -> None:
        if self._session:
            session_id = hex(id(self._session))
            logger.debug(f'Executing SQL COMMIT for Session ID: {session_id}')
            await self._session.commit()
            logger.debug(
                f'SQL COMMIT executed successfully for Session ID: {session_id}'
            )
        else:
            logger.warning('Commit attempted on a missing or inactive session')

    async def rollback(self) -> None:
        if self._session:
            session_id = hex(id(self._session))
            logger.debug(f'Executing SQL ROLLBACK for Session ID: {session_id}')
            await self._session.rollback()
            logger.debug(
                f'SQL ROLLBACK executed successfully for Session ID: {session_id}'
            )
        else:
            logger.warning('Rollback attempted on a missing or inactive session')
