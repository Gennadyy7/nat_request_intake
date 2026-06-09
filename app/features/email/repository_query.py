from sqlalchemy import ColumnElement
from sqlalchemy.orm import InstrumentedAttribute

from app.features.email.models import EmailMessage, EmailSender
from app.features.email.query_params import EmailMessageFilters, EmailSenderFilters
from app.features.nat.query_params import SortParams
from app.features.nat.repository_query import escape_ilike_pattern


def build_email_sender_filter_clauses(
    filters: EmailSenderFilters,
) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if filters.email is not None:
        pattern = f'%{escape_ilike_pattern(filters.email)}%'
        clauses.append(EmailSender.email.ilike(pattern))
    if filters.is_active is not None:
        clauses.append(EmailSender.is_active.is_(filters.is_active))
    return clauses


def build_email_message_filter_clauses(
    filters: EmailMessageFilters,
) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if filters.sender_email is not None:
        pattern = f'%{escape_ilike_pattern(filters.sender_email)}%'
        clauses.append(EmailMessage.sender_email.ilike(pattern))
    if filters.processing_status is not None:
        clauses.append(
            EmailMessage.processing_status == filters.processing_status.value
        )
    if filters.reply_status_is_null:
        clauses.append(EmailMessage.reply_status.is_(None))
    elif filters.reply_status is not None:
        clauses.append(EmailMessage.reply_status == filters.reply_status.value)
    if filters.received_at_from is not None:
        clauses.append(EmailMessage.received_at >= filters.received_at_from)
    if filters.received_at_to is not None:
        clauses.append(EmailMessage.received_at <= filters.received_at_to)
    return clauses


def sender_sort_column(sort: SortParams) -> InstrumentedAttribute[object]:
    return {
        'email': EmailSender.email,
        'name': EmailSender.name,
        'created_at': EmailSender.created_at,
        'updated_at': EmailSender.updated_at,
    }[sort.sort_by]


def message_sort_column(sort: SortParams) -> InstrumentedAttribute[object]:
    return {
        'received_at': EmailMessage.received_at,
        'sender_email': EmailMessage.sender_email,
    }[sort.sort_by]
