from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repositories.sqlalchemy import SQLAlchemyRepository
from app.features.email.models import EmailMessage, EmailSender
from app.features.email.query_params import EmailMessageFilters, EmailSenderFilters
from app.features.email.repository_query import (
    build_email_message_filter_clauses,
    build_email_sender_filter_clauses,
    message_sort_column,
    sender_sort_column,
)
from app.features.email.schemas import normalize_email
from app.features.nat.query_params import SortParams
from app.features.nat.repository_query import order_by_sort_column


class EmailSenderRepository(SQLAlchemyRepository[EmailSender, UUID]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(model=EmailSender, session=session)

    async def get_by_email(self, email: str) -> EmailSender | None:
        normalized = normalize_email(email)
        statement = select(EmailSender).where(EmailSender.email == normalized)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_active_sender_emails(self) -> frozenset[str]:
        statement = select(EmailSender.email).where(EmailSender.is_active.is_(True))
        result = await self._session.execute(statement)
        return frozenset(result.scalars().all())

    async def count_filtered(self, filters: EmailSenderFilters) -> int:
        clauses = build_email_sender_filter_clauses(filters)
        statement = select(func.count()).select_from(EmailSender)
        if clauses:
            statement = statement.where(*clauses)
        result = await self._session.execute(statement)
        return int(result.scalar_one())

    async def list_filtered(
        self,
        filters: EmailSenderFilters,
        sort: SortParams,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[EmailSender]:
        clauses = build_email_sender_filter_clauses(filters)
        statement = (
            select(EmailSender)
            .order_by(
                order_by_sort_column(sender_sort_column(sort), sort.sort_order),
                EmailSender.email.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        if clauses:
            statement = statement.where(*clauses)
        result = await self._session.execute(statement)
        return list(result.scalars().all())


class EmailMessageRepository(SQLAlchemyRepository[EmailMessage, UUID]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(model=EmailMessage, session=session)

    async def exists_by_message_id(self, message_id: str) -> bool:
        statement = select(
            exists().where(EmailMessage.message_id == message_id),
        )
        result = await self._session.execute(statement)
        return bool(result.scalar())

    async def get_by_nat_intake_id(self, nat_intake_id: UUID) -> EmailMessage | None:
        statement = (
            select(EmailMessage)
            .where(EmailMessage.nat_intake_id == nat_intake_id)
            .order_by(EmailMessage.received_at.desc())
            .limit(1)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def count_filtered(self, filters: EmailMessageFilters) -> int:
        clauses = build_email_message_filter_clauses(filters)
        statement = select(func.count()).select_from(EmailMessage)
        if clauses:
            statement = statement.where(*clauses)
        result = await self._session.execute(statement)
        return int(result.scalar_one())

    async def list_filtered(
        self,
        filters: EmailMessageFilters,
        sort: SortParams,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[EmailMessage]:
        clauses = build_email_message_filter_clauses(filters)
        statement = select(EmailMessage).order_by(
            order_by_sort_column(message_sort_column(sort), sort.sort_order),
            EmailMessage.id.desc(),
        )
        if clauses:
            statement = statement.where(*clauses)
        statement = statement.limit(limit).offset(offset)
        result = await self._session.execute(statement)
        return list(result.scalars().all())
