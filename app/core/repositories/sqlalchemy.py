from collections.abc import Sequence
from typing import TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base
from app.core.logging import get_logger
from app.core.repositories.protocol import RepositoryProtocol

logger = get_logger(__name__)

T = TypeVar('T', bound=Base)
ID_contra = TypeVar('ID_contra', contravariant=True, bound=int | str | UUID)


class SQLAlchemyRepository[T, ID_contra](RepositoryProtocol[T, ID_contra]):
    def __init__(self, model: type[T], session: AsyncSession):
        self._model = model
        self._session = session
        logger.debug(
            f'Initialized {self.__class__.__name__} for model "{self._model.__name__}" '
            f'[Session ID: {hex(id(self._session))}]'
        )

    async def get_by_id(self, entity_id: ID_contra) -> T | None:
        session_id = hex(id(self._session))
        logger.debug(
            f'[{self._model.__name__}] Fetching entity by ID: {entity_id} '
            f'[Session ID: {session_id}]'
        )
        result = await self._session.get(self._model, entity_id)

        if result:
            logger.debug(f'[{self._model.__name__}] Found entity with ID: {entity_id}')
        else:
            logger.debug(
                f'[{self._model.__name__}] Entity with ID: {entity_id} not found'
            )
        return result

    async def get_all(self, limit: int, offset: int) -> Sequence[T]:
        session_id = hex(id(self._session))
        stmt = select(self._model).limit(limit).offset(offset)

        logger.debug(
            f'[{self._model.__name__}] Executing get_all query: {stmt} '
            f'(limit={limit}, offset={offset}) [Session ID: {session_id}]'
        )

        result = await self._session.execute(stmt)
        entities = list(result.scalars().all())

        logger.debug(f'[{self._model.__name__}] Retrieved {len(entities)} records')
        return entities

    async def create(self, entity: T) -> T:
        session_id = hex(id(self._session))
        logger.debug(
            f'[{self._model.__name__}] Adding new entity to identity map '
            f'[Session ID: {session_id}]'
        )

        self._session.add(entity)

        logger.debug(f'[{self._model.__name__}] Executing flush for new entity')
        await self._session.flush()

        entity_id = getattr(entity, 'id', 'N/A')
        logger.debug(
            f'[{self._model.__name__}] Entity created and flushed successfully. Assigned ID: {entity_id}'
        )
        return entity

    async def update(self, entity: T) -> T:
        session_id = hex(id(self._session))
        entity_id = getattr(entity, 'id', 'N/A')
        logger.debug(
            f'[{self._model.__name__}] Updating entity ID: {entity_id} '
            f'[Session ID: {session_id}]'
        )

        logger.debug(f'[{self._model.__name__}] Executing flush for update')
        await self._session.flush()

        logger.debug(f'[{self._model.__name__}] Refreshing entity attributes from DB')
        await self._session.refresh(entity)

        logger.debug(
            f'[{self._model.__name__}] Entity ID: {entity_id} updated and refreshed successfully'
        )
        return entity

    async def delete(self, entity: T) -> bool:
        session_id = hex(id(self._session))
        entity_id = getattr(entity, 'id', 'N/A')
        logger.debug(
            f'[{self._model.__name__}] Attempting to delete entity ID: {entity_id} '
            f'[Session ID: {session_id}]'
        )

        try:
            await self._session.delete(entity)
            logger.debug(f'[{self._model.__name__}] Executing flush for delete')
            await self._session.flush()
            logger.debug(
                f'[{self._model.__name__}] Entity ID: {entity_id} deleted successfully from DB'
            )
            return True
        except SQLAlchemyError as e:
            logger.exception(
                f'[{self._model.__name__}] Failed to delete entity ID: {entity_id} '
                f'[Session ID: {session_id}]. Error: {e}'
            )
            return False
