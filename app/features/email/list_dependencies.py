from datetime import datetime
from typing import Annotated

from fastapi import HTTPException, Query, status

from app.features.email.constants import EmailApiErrorCode, EmailProcessingStatus
from app.features.email.messages import get_message
from app.features.email.query_params import (
    EMAIL_MESSAGE_SORT_COLUMNS,
    EMAIL_SENDER_SORT_COLUMNS,
    EmailMessageFilters,
    EmailSenderFilters,
)
from app.features.email.reply_status_filter_parsing import parse_reply_status_filter
from app.features.email.schemas import normalize_email
from app.features.nat.pagination import resolve_sort_params
from app.features.nat.query_params import SortParams


def get_email_sender_filters(
    filter_email: Annotated[str | None, Query()] = None,
    filter_is_active: Annotated[bool | None, Query()] = None,
) -> EmailSenderFilters:
    email: str | None = None
    if filter_email is not None:
        normalized = normalize_email(filter_email)
        if normalized:
            email = normalized
    return EmailSenderFilters(email=email, is_active=filter_is_active)


def get_email_sender_sort_params(
    sort_by: Annotated[str | None, Query()] = None,
    sort_order: Annotated[str | None, Query()] = None,
) -> SortParams:
    return resolve_sort_params(
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_columns=EMAIL_SENDER_SORT_COLUMNS,
        default_sort_by='email',
        default_sort_order='asc',
    )


def get_email_message_sort_params(
    sort_by: Annotated[str | None, Query()] = None,
    sort_order: Annotated[str | None, Query()] = None,
) -> SortParams:
    return resolve_sort_params(
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_columns=EMAIL_MESSAGE_SORT_COLUMNS,
        default_sort_by='received_at',
        default_sort_order='desc',
    )


def get_email_message_filters(
    filter_sender_email: Annotated[str | None, Query()] = None,
    filter_processing_status: Annotated[str | None, Query()] = None,
    filter_reply_status: Annotated[str | None, Query()] = None,
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
    reply_status_filter = parse_reply_status_filter(filter_reply_status)
    sender_email: str | None = None
    if filter_sender_email is not None:
        normalized = normalize_email(filter_sender_email)
        if normalized:
            sender_email = normalized
    return EmailMessageFilters(
        sender_email=sender_email,
        processing_status=processing_status,
        reply_status=reply_status_filter.eq_value,
        reply_status_is_null=reply_status_filter.is_null,
        received_at_from=filter_received_at_from,
        received_at_to=filter_received_at_to,
    )
