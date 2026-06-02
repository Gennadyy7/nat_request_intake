from typing import NoReturn
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.email.constants import EmailApiErrorCode
from app.features.email.messages import get_message
from app.features.email.models import EmailSender
from app.features.email.schemas import (
    EmailSenderCreate,
    EmailSenderResponse,
    EmailSenderUpdate,
)
from app.features.nat.pagination import PaginationParams, build_paginated_response
from app.features.nat.schemas.pagination import PaginatedResponse


class EmailSenderService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def create(self, payload: EmailSenderCreate) -> EmailSenderResponse:
        existing = await self._uow.email_senders.get_by_email(str(payload.email))
        if existing is not None:
            self._raise_sender_exists()

        entity = EmailSender(
            id=uuid4(),
            email=str(payload.email),
            name=payload.name,
            contact=payload.contact,
            is_active=payload.is_active,
        )
        try:
            await self._uow.email_senders.create(entity)
        except IntegrityError:
            await self._uow.rollback()
            self._raise_sender_exists()
        await self._uow.commit()
        return EmailSenderResponse.model_validate(entity)

    async def get(self, sender_id: UUID) -> EmailSenderResponse:
        entity = await self._uow.email_senders.get_by_id(sender_id)
        if entity is None:
            self._raise_sender_not_found(sender_id)
        return EmailSenderResponse.model_validate(entity)

    async def list(
        self,
        pagination: PaginationParams,
    ) -> PaginatedResponse[EmailSenderResponse]:
        total = await self._uow.email_senders.count_all()
        entities = await self._uow.email_senders.list_ordered(
            limit=pagination.limit,
            offset=pagination.offset,
        )
        items = [EmailSenderResponse.model_validate(entity) for entity in entities]
        return build_paginated_response(
            items,
            total_items=total,
            page=pagination.page,
            limit=pagination.limit,
        )

    async def update(
        self,
        sender_id: UUID,
        payload: EmailSenderUpdate,
    ) -> EmailSenderResponse:
        entity = await self._uow.email_senders.get_by_id(sender_id)
        if entity is None:
            self._raise_sender_not_found(sender_id)

        if payload.email is not None:
            normalized = str(payload.email)
            existing = await self._uow.email_senders.get_by_email(normalized)
            if existing is not None and existing.id != sender_id:
                self._raise_sender_exists()
            entity.email = normalized
        if payload.name is not None:
            entity.name = payload.name
        if payload.contact is not None:
            entity.contact = payload.contact
        if payload.is_active is not None:
            entity.is_active = payload.is_active

        try:
            await self._uow.email_senders.update(entity)
        except IntegrityError:
            await self._uow.rollback()
            self._raise_sender_exists()
        await self._uow.commit()
        return EmailSenderResponse.model_validate(entity)

    async def delete(self, sender_id: UUID) -> None:
        entity = await self._uow.email_senders.get_by_id(sender_id)
        if entity is None:
            self._raise_sender_not_found(sender_id)
        await self._uow.email_senders.delete(entity)
        await self._uow.commit()

    def _raise_sender_not_found(self, sender_id: UUID) -> NoReturn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'error_code': EmailApiErrorCode.SENDER_NOT_FOUND,
                'message': get_message(EmailApiErrorCode.SENDER_NOT_FOUND),
                'sender_id': str(sender_id),
            },
        )

    def _raise_sender_exists(self) -> NoReturn:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                'error_code': EmailApiErrorCode.SENDER_ALREADY_EXISTS,
                'message': get_message(EmailApiErrorCode.SENDER_ALREADY_EXISTS),
            },
        )
