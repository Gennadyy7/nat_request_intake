from sqlalchemy import ColumnElement

from app.features.email.models import EmailMessage
from app.features.email.query_params import EmailMessageFilters
from app.features.nat.repository_query import escape_ilike_pattern


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
    if filters.received_at_from is not None:
        clauses.append(EmailMessage.received_at >= filters.received_at_from)
    if filters.received_at_to is not None:
        clauses.append(EmailMessage.received_at <= filters.received_at_to)
    return clauses
