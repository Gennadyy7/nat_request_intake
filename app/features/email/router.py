from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from fastapi_keycloak_middleware import get_user

from app.features.auth.schemas import User
from app.features.email.dependencies import (
    EmailMessageQueryServiceDep,
    EmailSenderServiceDep,
)
from app.features.email.list_dependencies import (
    get_email_message_filters,
    get_pagination_params,
)
from app.features.email.query_params import EmailMessageFilters
from app.features.email.schemas import (
    EmailMessageListItem,
    EmailMessageResponse,
    EmailSenderCreate,
    EmailSenderResponse,
    EmailSenderUpdate,
)
from app.features.nat.pagination import PaginationParams
from app.features.nat.schemas.pagination import PaginatedResponse

router = APIRouter(prefix='/email', tags=['email'])


@router.post(
    '/senders',
    response_model=EmailSenderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_sender(
    _user: Annotated[User, Depends(get_user)],
    payload: EmailSenderCreate,
    service: EmailSenderServiceDep,
) -> EmailSenderResponse:
    return await service.create(payload)


@router.get('/senders', response_model=PaginatedResponse[EmailSenderResponse])
async def list_senders(
    _user: Annotated[User, Depends(get_user)],
    service: EmailSenderServiceDep,
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
) -> PaginatedResponse[EmailSenderResponse]:
    return await service.list(pagination)


@router.get('/senders/{sender_id}', response_model=EmailSenderResponse)
async def get_sender(
    sender_id: UUID,
    _user: Annotated[User, Depends(get_user)],
    service: EmailSenderServiceDep,
) -> EmailSenderResponse:
    return await service.get(sender_id)


@router.patch('/senders/{sender_id}', response_model=EmailSenderResponse)
async def update_sender(
    sender_id: UUID,
    payload: EmailSenderUpdate,
    _user: Annotated[User, Depends(get_user)],
    service: EmailSenderServiceDep,
) -> EmailSenderResponse:
    return await service.update(sender_id, payload)


@router.delete('/senders/{sender_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_sender(
    sender_id: UUID,
    _user: Annotated[User, Depends(get_user)],
    service: EmailSenderServiceDep,
) -> Response:
    await service.delete(sender_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/messages', response_model=PaginatedResponse[EmailMessageListItem])
async def list_messages(
    _user: Annotated[User, Depends(get_user)],
    service: EmailMessageQueryServiceDep,
    filters: Annotated[EmailMessageFilters, Depends(get_email_message_filters)],
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
) -> PaginatedResponse[EmailMessageListItem]:
    return await service.list(filters, pagination)


@router.get('/messages/{message_id}', response_model=EmailMessageResponse)
async def get_message(
    message_id: UUID,
    _user: Annotated[User, Depends(get_user)],
    service: EmailMessageQueryServiceDep,
) -> EmailMessageResponse:
    return await service.get(message_id)
