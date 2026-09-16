from email.message import EmailMessage
import re
from uuid import UUID

from app.features.nat.constants import IntakeStatus
from app.features.nat.schemas.intake import IntakeResponse
from email_poller.app.core.config import settings
from email_poller.app.features.email_reply.messages import (
    INTAKE_STATUS_LABELS,
    REJECTED_MESSAGE_FALLBACK,
    REPLY_SUBJECT_WHEN_MISSING,
)

_REPLY_PREFIX_RE = re.compile(r'^re:\s*', re.IGNORECASE)


def build_intake_reply_message(
    *,
    intake: IntakeResponse,
    sender_email: str,
    original_subject: str | None,
    original_message_id: str,
) -> EmailMessage:
    if intake.status not in INTAKE_STATUS_LABELS:
        raise ValueError(f'Intake status does not support email reply: {intake.status}')

    message = EmailMessage()
    message['Subject'] = build_reply_subject(original_subject)
    message['From'] = settings.IMAP_USER
    message['To'] = sender_email
    message['Reply-To'] = str(settings.EMAIL_REPLY_TO)

    normalized_message_id = normalize_message_id(original_message_id)
    message['In-Reply-To'] = normalized_message_id
    message['References'] = normalized_message_id

    message.set_content(build_intake_reply_body(intake), charset='utf-8')
    return message


def build_reply_subject(original_subject: str | None) -> str:
    if original_subject is None or not original_subject.strip():
        return REPLY_SUBJECT_WHEN_MISSING
    subject = original_subject.strip()
    if _REPLY_PREFIX_RE.match(subject):
        return subject
    return f'Re: {subject}'


def normalize_message_id(message_id: str) -> str:
    cleaned = message_id.strip()
    if not cleaned:
        raise ValueError('Message-ID must not be empty')
    if cleaned.startswith('<') and cleaned.endswith('>'):
        return cleaned
    return f'<{cleaned.strip("<>")}>'


def build_intake_reply_body(intake: IntakeResponse) -> str:
    status_label = INTAKE_STATUS_LABELS[intake.status]
    lines = [
        'Результат обработки заявки',
        '',
        f'Статус: {status_label}',
    ]

    if intake.status == IntakeStatus.REJECTED:
        lines.extend(
            [
                f'Идентификатор заявки: {intake.intake_id}',
                f'Файл: {intake.file_name}',
                f'Причина: {_rejected_reason(intake)}',
            ]
        )
        return '\n'.join(lines)

    lines.extend(
        [
            f'Идентификатор заявки: {intake.intake_id}',
            f'Идентификатор пакета: {_format_batch_id(intake.batch_id)}',
            f'Файл: {intake.file_name}',
            f'Всего строк: {intake.total_data_rows}',
            f'Принято строк: {intake.valid_rows}',
            f'Отклонено строк: {intake.rejected_rows}',
        ]
    )
    return '\n'.join(lines)


def _rejected_reason(intake: IntakeResponse) -> str:
    if intake.message and intake.message.strip():
        return intake.message.strip()
    return REJECTED_MESSAGE_FALLBACK


def _format_batch_id(batch_id: UUID | None) -> str:
    if batch_id is None:
        return 'не указан'
    return str(batch_id)
