from datetime import datetime
from typing import Annotated

from fastapi import HTTPException, Query, status

from app.features.email.constants import EmailApiErrorCode, EmailProcessingStatus
from app.features.email.messages import get_message
from app.features.email.query_params import EmailMessageFilters


def get_email_message_filters(
    filter_sender_email: Annotated[str | None, Query()] = None,
    filter_processing_status: Annotated[str | None, Query()] = None,
    filter_received_at_from: Annotated[datetime | None, Query()] = None,
    filter_received_at_to: Annotated[datetime | None, Query()] = None,
) -> EmailMessageFilters:
    processing_status: EmailProcessingStatus | None = None
    if filter_processing_status is not None:
        try:
            processing_status = EmailProcessingStatus(filter_processing_status)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    'error_code': EmailApiErrorCode.INVALID_FILTER_PROCESSING_STATUS,
                    'message': get_message(
                        EmailApiErrorCode.INVALID_FILTER_PROCESSING_STATUS
                    ),
                    'filter_processing_status': filter_processing_status,
                    'allowed': [member.value for member in EmailProcessingStatus],
                },
            ) from exc
    return EmailMessageFilters(
        sender_email=filter_sender_email,
        processing_status=processing_status,
        received_at_from=filter_received_at_from,
        received_at_to=filter_received_at_to,
    )
