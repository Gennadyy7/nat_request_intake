from dataclasses import dataclass
from datetime import UTC, datetime
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
import re

from app.features.email.schemas import normalize_email
from app.features.nat.constants import AllowedFileExtension
from app.features.nat.services.parsing.file_parser import resolve_extension

_HTML_TAG_RE = re.compile(r'<[^>]+>')


@dataclass(frozen=True, slots=True)
class EmailAttachment:
    filename: str
    content: bytes
    extension: AllowedFileExtension


@dataclass(frozen=True, slots=True)
class ParsedEmailHeaders:
    sender_email: str
    message_id: str
    received_at: datetime


@dataclass(frozen=True, slots=True)
class ParsedIncomingEmail:
    sender_email: str
    subject: str | None
    body: str | None
    received_at: datetime
    message_id: str
    attachment: EmailAttachment | None


def parse_rfc822_headers(
    raw_headers: bytes,
    *,
    surrogate_message_id: str,
) -> ParsedEmailHeaders:
    message = message_from_bytes(raw_headers)
    sender_email = _extract_sender_email(message)
    received_at = _extract_received_at(message)
    message_id = _extract_message_id(message) or surrogate_message_id
    return ParsedEmailHeaders(
        sender_email=sender_email,
        message_id=message_id,
        received_at=received_at,
    )


def parse_rfc822_message(
    raw_message: bytes,
    *,
    surrogate_message_id: str,
) -> ParsedIncomingEmail:
    message = message_from_bytes(raw_message)
    sender_email = _extract_sender_email(message)
    subject = _decode_subject(message.get('Subject'))
    body = _extract_body_text(message)
    received_at = _extract_received_at(message)
    message_id = _extract_message_id(message) or surrogate_message_id
    attachment = _find_first_allowed_attachment(message)
    return ParsedIncomingEmail(
        sender_email=sender_email,
        subject=subject,
        body=body,
        received_at=received_at,
        message_id=message_id,
        attachment=attachment,
    )


def _extract_sender_email(message: Message) -> str:
    from_header = message.get('From', '')
    _, address = parseaddr(from_header)
    if not address:
        raise ValueError('Email From header is missing or invalid')
    return normalize_email(address)


def _decode_subject(subject_header: str | None) -> str | None:
    if subject_header is None or not subject_header.strip():
        return None
    subject = str(make_header(decode_header(subject_header))).strip()
    return subject or None


def _extract_message_id(message: Message) -> str | None:
    raw = message.get('Message-ID') or message.get('Message-Id')
    if raw is None:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    return cleaned[:1000]


def _extract_received_at(message: Message) -> datetime:
    date_header = message.get('Date')
    if date_header:
        try:
            parsed = parsedate_to_datetime(date_header)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except (TypeError, ValueError, IndexError):
            pass
    return datetime.now(UTC)


def _extract_body_text(message: Message) -> str | None:
    if message.is_multipart():
        plain = _find_text_part(message, 'plain')
        if plain is not None:
            return plain
        html = _find_text_part(message, 'html')
        if html is not None:
            return _html_to_text(html)
        return None
    content_type = message.get_content_type()
    payload = _decode_payload(message)
    if payload is None:
        return None
    if content_type == 'text/plain':
        return payload
    if content_type == 'text/html':
        return _html_to_text(payload)
    return None


def _find_text_part(message: Message, subtype: str) -> str | None:
    for part in message.walk():
        if part.get_content_maintype() != 'text':
            continue
        if part.get_content_subtype() != subtype:
            continue
        if part.get_filename():
            continue
        decoded = _decode_payload(part)
        if decoded:
            return decoded
    return None


def _decode_payload(part: Message) -> str | None:
    payload = part.get_payload(decode=True)
    if not isinstance(payload, bytes):
        return None
    charset = part.get_content_charset() or 'utf-8'
    try:
        text = payload.decode(charset, errors='replace').strip()
    except LookupError:
        text = payload.decode('utf-8', errors='replace').strip()
    return text or None


def _html_to_text(html: str) -> str:
    without_tags = _HTML_TAG_RE.sub(' ', html)
    return ' '.join(without_tags.split())


def _find_first_allowed_attachment(message: Message) -> EmailAttachment | None:
    for part in message.walk():
        if part.get_content_disposition() not in {'attachment', 'inline', None}:
            continue
        filename = part.get_filename()
        if not filename:
            continue
        extension = resolve_extension(filename)
        if extension is None:
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes) or not payload:
            continue
        return EmailAttachment(
            filename=filename,
            content=payload,
            extension=extension,
        )
    return None
