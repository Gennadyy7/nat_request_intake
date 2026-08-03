from email.message import EmailMessage
import re
from uuid import UUID

from intake_result_email_worker.app.features.result_email.classification import (
    ResultEmailClassification,
    ResultEmailContext,
    stage_label,
)
from intake_result_email_worker.app.features.result_email.messages import (
    RESULT_SUBJECT_WHEN_MISSING,
    STATUS_FAILURE_LABEL,
    STATUS_SUCCESS_LABEL,
)

_REPLY_PREFIX_RE = re.compile(r'^re:\s*', re.IGNORECASE)


def build_result_email_message(
    *,
    context: ResultEmailContext,
    classification: ResultEmailClassification,
    from_addr: str,
    reply_to: str,
    attachment_bytes: bytes | None = None,
    attachment_filename: str | None = None,
    oversized_limit_bytes: int | None = None,
) -> EmailMessage:
    message = EmailMessage()
    message['Subject'] = build_result_subject(context.original_subject)
    message['From'] = from_addr
    message['To'] = context.sender_email
    message['Reply-To'] = reply_to

    if context.original_message_id is not None and context.original_message_id.strip():
        normalized_message_id = normalize_message_id(context.original_message_id)
        message['In-Reply-To'] = normalized_message_id
        message['References'] = normalized_message_id

    message.set_content(
        build_result_email_body(
            context=context,
            classification=classification,
            reply_to=reply_to,
            has_attachment=attachment_bytes is not None,
            oversized_limit_bytes=oversized_limit_bytes,
        ),
        charset='utf-8',
    )

    if attachment_bytes is not None:
        if attachment_filename is None or not attachment_filename.strip():
            raise ValueError('Attachment filename is required when attaching bytes')
        message.add_attachment(
            attachment_bytes,
            maintype='text',
            subtype='csv',
            filename=attachment_filename,
        )
    return message


def build_result_subject(original_subject: str | None) -> str:
    if original_subject is None or not original_subject.strip():
        return RESULT_SUBJECT_WHEN_MISSING
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


def build_result_email_body(
    *,
    context: ResultEmailContext,
    classification: ResultEmailClassification,
    reply_to: str,
    has_attachment: bool,
    oversized_limit_bytes: int | None,
) -> str:
    lines = [
        'Итог обработки заявки',
        '',
        f'Номер заявки: {context.intake_number}',
        f'Идентификатор заявки: {context.intake_id}',
        f'Идентификатор пакета: {_format_batch_id(context.batch_id)}',
        f'Файл: {context.file_name}',
    ]

    if classification.kind == 'failure':
        assert classification.stage is not None
        assert classification.reason is not None
        lines.extend(
            [
                f'Статус: {STATUS_FAILURE_LABEL}',
                f'Этап: {stage_label(classification.stage)}',
                f'Причина: {classification.reason}',
            ]
        )
        return '\n'.join(lines)

    lines.append(f'Статус: {STATUS_SUCCESS_LABEL}')
    if classification.found_count is not None:
        lines.append(f'Найдено в ASSOMI: {classification.found_count}')
    if classification.missing_count is not None:
        lines.append(f'Не найдено в ASSOMI: {classification.missing_count}')

    if classification.kind == 'success_oversized':
        assert oversized_limit_bytes is not None
        lines.extend(
            [
                (
                    'Файл не приложен: размер превышает допустимый лимит '
                    f'{oversized_limit_bytes} байт.'
                ),
                f'Обратитесь за помощью: {reply_to}',
            ]
        )
        return '\n'.join(lines)

    if has_attachment:
        lines.append('CSV-файл ASSOMI во вложении.')
    return '\n'.join(lines)


def _format_batch_id(batch_id: UUID) -> str:
    return str(batch_id)
