from typing import NamedTuple

from fastapi import HTTPException, status

from app.features.email.constants import (
    EMAIL_REPLY_FILTER_NULL_SENTINEL,
    EmailApiErrorCode,
    EmailReplyStatus,
)
from app.features.email.messages import get_message


class ReplyStatusFilter(NamedTuple):
    eq_value: EmailReplyStatus | None
    is_null: bool


def parse_reply_status_filter(raw: str | None) -> ReplyStatusFilter:
    if raw is None:
        return ReplyStatusFilter(eq_value=None, is_null=False)
    if raw == EMAIL_REPLY_FILTER_NULL_SENTINEL:
        return ReplyStatusFilter(eq_value=None, is_null=True)
    try:
        return ReplyStatusFilter(eq_value=EmailReplyStatus(raw), is_null=False)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                'code': EmailApiErrorCode.INVALID_FILTER_REPLY_STATUS,
                'message': get_message(EmailApiErrorCode.INVALID_FILTER_REPLY_STATUS),
                'filter_reply_status': raw,
                'allowed': [
                    *[member.value for member in EmailReplyStatus],
                    EMAIL_REPLY_FILTER_NULL_SENTINEL,
                ],
            },
        ) from exc
