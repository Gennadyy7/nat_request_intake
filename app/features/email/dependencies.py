from typing import Annotated

from fastapi import Depends

from app.core.dependencies import get_uow
from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.email.services.message_query_service import EmailMessageQueryService
from app.features.email.services.sender_service import EmailSenderService


def get_email_sender_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
) -> EmailSenderService:
    return EmailSenderService(uow)


def get_email_message_query_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
) -> EmailMessageQueryService:
    return EmailMessageQueryService(uow)


EmailSenderServiceDep = Annotated[EmailSenderService, Depends(get_email_sender_service)]
EmailMessageQueryServiceDep = Annotated[
    EmailMessageQueryService,
    Depends(get_email_message_query_service),
]
