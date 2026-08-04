from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.assomi.repositories import AssomiTaskRepository
from app.features.email.repositories import (
    EmailMessageRepository,
    EmailSenderRepository,
)
from app.features.nat.repositories import (
    NatBatchRepository,
    NatDedupKeyRepository,
    NatGlobalProcessingRepository,
    NatIntakeRepository,
    NatIntakeRowErrorRepository,
    NatResultProcessingTaskRepository,
    NatTaskRepository,
)

logger = get_logger(__name__)


class SQLAlchemyUnitOfWork(UnitOfWorkProtocol):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._nat_intakes: NatIntakeRepository | None = None
        self._nat_intake_row_errors: NatIntakeRowErrorRepository | None = None
        self._nat_batches: NatBatchRepository | None = None
        self._nat_global_processing: NatGlobalProcessingRepository | None = None
        self._nat_tasks: NatTaskRepository | None = None
        self._nat_result_processing_tasks: NatResultProcessingTaskRepository | None = (
            None
        )
        self._nat_dedup_keys: NatDedupKeyRepository | None = None
        self._assomi_tasks: AssomiTaskRepository | None = None
        self._email_senders: EmailSenderRepository | None = None
        self._email_messages: EmailMessageRepository | None = None
        self._committed = False
        logger.debug('SQLAlchemyUnitOfWork initialized with session factory')

    @property
    def nat_intakes(self) -> NatIntakeRepository:
        if self._nat_intakes is None:
            logger.error(
                'Attempted to access nat_intakes repository outside of context manager block'
            )
            raise RuntimeError(
                'UnitOfWork context is not active. Access attributes inside an "async with" block.'
            )
        return self._nat_intakes

    @property
    def nat_intake_row_errors(self) -> NatIntakeRowErrorRepository:
        if self._nat_intake_row_errors is None:
            logger.error(
                'Attempted to access nat_intake_row_errors repository outside of context manager block'
            )
            raise RuntimeError(
                'UnitOfWork context is not active. Access attributes inside an "async with" block.'
            )
        return self._nat_intake_row_errors

    @property
    def nat_batches(self) -> NatBatchRepository:
        if self._nat_batches is None:
            logger.error(
                'Attempted to access nat_batches repository outside of context manager block'
            )
            raise RuntimeError(
                'UnitOfWork context is not active. Access attributes inside an "async with" block.'
            )
        return self._nat_batches

    @property
    def nat_global_processing(self) -> NatGlobalProcessingRepository:
        if self._nat_global_processing is None:
            logger.error(
                'Attempted to access nat_global_processing repository '
                'outside of context manager block'
            )
            raise RuntimeError(
                'UnitOfWork context is not active. Access attributes inside an "async with" block.'
            )
        return self._nat_global_processing

    @property
    def nat_tasks(self) -> NatTaskRepository:
        if self._nat_tasks is None:
            logger.error(
                'Attempted to access nat_tasks repository outside of context manager block'
            )
            raise RuntimeError(
                'UnitOfWork context is not active. Access attributes inside an "async with" block.'
            )
        return self._nat_tasks

    @property
    def nat_result_processing_tasks(self) -> NatResultProcessingTaskRepository:
        if self._nat_result_processing_tasks is None:
            logger.error(
                'Attempted to access nat_result_processing_tasks repository '
                'outside of context manager block'
            )
            raise RuntimeError(
                'UnitOfWork context is not active. Access attributes inside an "async with" block.'
            )
        return self._nat_result_processing_tasks

    @property
    def nat_dedup_keys(self) -> NatDedupKeyRepository:
        if self._nat_dedup_keys is None:
            logger.error(
                'Attempted to access nat_dedup_keys repository outside of context manager block'
            )
            raise RuntimeError(
                'UnitOfWork context is not active. Access attributes inside an "async with" block.'
            )
        return self._nat_dedup_keys

    @property
    def assomi_tasks(self) -> AssomiTaskRepository:
        if self._assomi_tasks is None:
            logger.error(
                'Attempted to access assomi_tasks repository outside of context manager block'
            )
            raise RuntimeError(
                'UnitOfWork context is not active. Access attributes inside an "async with" block.'
            )
        return self._assomi_tasks

    @property
    def email_senders(self) -> EmailSenderRepository:
        if self._email_senders is None:
            logger.error(
                'Attempted to access email_senders repository outside of context manager block'
            )
            raise RuntimeError(
                'UnitOfWork context is not active. Access attributes inside an "async with" block.'
            )
        return self._email_senders

    @property
    def email_messages(self) -> EmailMessageRepository:
        if self._email_messages is None:
            logger.error(
                'Attempted to access email_messages repository outside of context manager block'
            )
            raise RuntimeError(
                'UnitOfWork context is not active. Access attributes inside an "async with" block.'
            )
        return self._email_messages

    async def __aenter__(self) -> Self:
        logger.debug('Entering UnitOfWork context: opening new database session')
        self._session = self._session_factory()
        assert self._session is not None
        logger.debug(
            f'Database session opened successfully. Session ID: {hex(id(self._session))}'
        )
        self._nat_intakes = NatIntakeRepository(self._session)
        self._nat_intake_row_errors = NatIntakeRowErrorRepository(self._session)
        self._nat_batches = NatBatchRepository(self._session)
        self._nat_global_processing = NatGlobalProcessingRepository(self._session)
        self._nat_tasks = NatTaskRepository(self._session)
        self._nat_result_processing_tasks = NatResultProcessingTaskRepository(
            self._session,
        )
        self._nat_dedup_keys = NatDedupKeyRepository(self._session)
        self._assomi_tasks = AssomiTaskRepository(self._session)
        self._email_senders = EmailSenderRepository(self._session)
        self._email_messages = EmailMessageRepository(self._session)
        self._committed = False
        logger.debug(
            'Nat, ASSOMI and email repositories initialized for UnitOfWork session'
        )
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
            elif not self._committed:
                logger.debug(
                    f'UnitOfWork exiting without commit for Session ID: {session_id}. '
                    'Triggering rollback.'
                )
                await self.rollback()
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
            self._committed = True
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
