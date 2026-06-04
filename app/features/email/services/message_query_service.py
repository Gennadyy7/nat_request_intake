from typing import NoReturn
from uuid import UUID

from fastapi import HTTPException, status

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.email.constants import EmailApiErrorCode
from app.features.email.messages import get_message
from app.features.email.query_params import EmailMessageFilters
from app.features.email.schemas import EmailMessageListItem, EmailMessageResponse
from app.features.nat.pagination import PaginationParams, build_paginated_response
from app.features.nat.schemas.pagination import PaginatedResponse


class EmailMessageQueryService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def get(self, message_id: UUID) -> EmailMessageResponse:
        entity = await self._uow.email_messages.get_by_id(message_id)
        if entity is None:
            self._raise_message_not_found(message_id)
        return EmailMessageResponse.model_validate(entity)

    async def list(
        self,
        filters: EmailMessageFilters,
        pagination: PaginationParams,
    ) -> PaginatedResponse[EmailMessageListItem]:
        total = await self._uow.email_messages.count_filtered(filters)
        entities = await self._uow.email_messages.list_filtered(
            filters,
            limit=pagination.limit,
            offset=pagination.offset,
        )
        items = [EmailMessageListItem.model_validate(entity) for entity in entities]
        return build_paginated_response(
            items,
            total_items=total,
            page=pagination.page,
            limit=pagination.limit,
        )

    def _raise_message_not_found(self, message_id: UUID) -> NoReturn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'error_code': EmailApiErrorCode.MESSAGE_NOT_FOUND,
                'message': get_message(EmailApiErrorCode.MESSAGE_NOT_FOUND),
                'message_id': str(message_id),
            },
        )
