from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

POSTGRES_INDEXES_NAMING_CONVENTION = {
    'ix': 'ix_%(column_0_label)s',
    'uq': 'uq_%(table_name)s_%(column_0_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'pk': 'pk_%(table_name)s',
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)


class TimestampMixin:
    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class DatabaseManager:
    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    def init(
        self,
        *,
        database_url: str | None = None,
        db_echo: bool | None = None,
        pool_size: int | None = None,
        max_overflow: int | None = None,
        pool_recycle: int | None = None,
    ) -> None:
        if self._engine is not None:
            return

        self._engine = create_async_engine(
            database_url if database_url is not None else settings.DB_URL,
            echo=db_echo if db_echo is not None else settings.DB_ECHO,
            pool_pre_ping=True,
            pool_size=pool_size if pool_size is not None else settings.DB_POOL_SIZE,
            max_overflow=(
                max_overflow if max_overflow is not None else settings.DB_MAX_OVERFLOW
            ),
            pool_recycle=(
                pool_recycle if pool_recycle is not None else settings.DB_POOL_RECYCLE
            ),
        )

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        logger.info('Database engine initialized')

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info('Database connections closed')

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        if self._session_factory is None:
            logger.error('Database not initialized')
            raise RuntimeError('Database not initialized. Call init() first.')

        async with self._session_factory() as session:
            yield session

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            logger.error('Database engine not initialized')
            raise RuntimeError('Database engine not initialized')
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            logger.error('Session factory not initialized')
            raise RuntimeError('Session factory not initialized')
        return self._session_factory


db_manager = DatabaseManager()
