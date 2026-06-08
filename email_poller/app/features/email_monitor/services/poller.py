from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.unit_of_work.sqlalchemy import SQLAlchemyUnitOfWork
from app.features.email.constants import (
    EMAIL_PARSE_FAILURE_SENDER,
    EmailProcessingStatus,
    EmailReplyStatus,
    EmailSkipReason,
)
from app.features.email.messages import get_message
from app.features.email.models import EmailMessage
from app.features.email.schemas import normalize_email
from app.features.nat.constants import IntakeStatus
from app.features.nat.schemas.intake import IntakeResponse
from email_poller.app.core.config import settings
from email_poller.app.core.database import db_manager
from email_poller.app.core.logging import get_logger
from email_poller.app.core.nat_client import NatIntakeClient, NatIntakeTransportError
from email_poller.app.features.email_monitor.imap.client import (
    ImapClientError,
    ImapMailboxClient,
)
from email_poller.app.features.email_monitor.imap.parser import (
    ParsedIncomingEmail,
    parse_rfc822_message,
)
from email_poller.app.features.email_reply.service import EmailReplyService

logger = get_logger(__name__)

_INTAKE_STATUSES_REQUIRING_REPLY = frozenset(
    {
        IntakeStatus.ACCEPTED,
        IntakeStatus.PARTIALLY_ACCEPTED,
        IntakeStatus.REJECTED,
    },
)


@dataclass(frozen=True, slots=True)
class _EmailAuditFields:
    sender_email: str
    message_id: str
    subject: str | None
    body: str | None
    received_at: datetime


class EmailPollService:
    def __init__(
        self,
        nat_client: NatIntakeClient,
        reply_service: EmailReplyService,
    ) -> None:
        self._nat_client = nat_client
        self._reply_service = reply_service

    async def poll_once(self) -> None:
        logger.info('Email poll cycle started')
        async with ImapMailboxClient() as imap:
            allowed_senders = await self._load_active_sender_emails()
            logger.info(
                'Loaded {} active sender(s) into whitelist',
                len(allowed_senders),
            )
            logger.debug('Whitelist senders={}', sorted(allowed_senders)[:50])
            unseen_uids = await imap.list_unseen_uids()
            if not unseen_uids:
                logger.info('No unseen IMAP messages')
                logger.info('Email poll cycle finished')
                return

            logger.info('Processing {} unseen IMAP message(s)', len(unseen_uids))
            for uid in unseen_uids:
                await self._process_uid(imap, uid, allowed_senders)
        logger.info('Email poll cycle finished')

    async def _load_active_sender_emails(self) -> frozenset[str]:
        async with SQLAlchemyUnitOfWork(db_manager.session_factory) as uow:
            return await uow.email_senders.get_active_sender_emails()

    async def _process_uid(
        self,
        imap: ImapMailboxClient,
        uid: str,
        allowed_senders: frozenset[str],
    ) -> None:
        logger.info('IMAP processing started: uid={}', uid)
        try:
            raw_message = await imap.fetch_rfc822(uid)
        except ImapClientError:
            logger.exception('Failed to fetch IMAP uid={}', uid)
            return

        surrogate_message_id = _surrogate_message_id(uid)
        try:
            parsed = parse_rfc822_message(
                raw_message,
                surrogate_message_id=surrogate_message_id,
            )
        except ValueError:
            logger.exception(
                'Failed to parse email uid={} surrogate_message_id={}',
                uid,
                surrogate_message_id,
            )
            skip_code, skip_message = _skip_error_fields(EmailSkipReason.PARSE_FAILED)
            await self._persist_and_mark_seen(
                imap,
                uid,
                _EmailAuditFields(
                    sender_email=EMAIL_PARSE_FAILURE_SENDER,
                    message_id=surrogate_message_id,
                    subject=None,
                    body=None,
                    received_at=datetime.now(UTC),
                ),
                processing_status=EmailProcessingStatus.SKIPPED,
                nat_intake_id=None,
                error_code=skip_code,
                error_message=skip_message,
            )
            return

        fields = _fields_from_parsed(parsed)
        logger.info(
            'Email parsed: uid={} message_id={} sender={} subject_present={} '
            'body_chars={} attachment_present={}',
            uid,
            fields.message_id,
            parsed.sender_email,
            bool(fields.subject),
            len(fields.body or ''),
            parsed.attachment is not None,
        )
        if parsed.attachment is not None:
            logger.info(
                'Attachment selected: uid={} filename={} bytes={} ext={}',
                uid,
                parsed.attachment.filename,
                len(parsed.attachment.content),
                parsed.attachment.extension,
            )

        if await self._is_duplicate(fields.message_id):
            logger.info(
                'Skipping duplicate message_id={} uid={}',
                fields.message_id,
                uid,
            )
            await imap.mark_seen(uid)
            return

        if parsed.sender_email not in allowed_senders:
            logger.info(
                'Skipping non-whitelisted sender={} uid={}',
                parsed.sender_email,
                uid,
            )
            skip_code, skip_message = _skip_error_fields(
                EmailSkipReason.SENDER_NOT_WHITELISTED,
            )
            await self._persist_and_mark_seen(
                imap,
                uid,
                fields,
                processing_status=EmailProcessingStatus.SKIPPED,
                nat_intake_id=None,
                error_code=skip_code,
                error_message=skip_message,
            )
            return

        if parsed.attachment is None:
            logger.info(
                'Skipping email without allowed attachment sender={} uid={}',
                parsed.sender_email,
                uid,
            )
            skip_code, skip_message = _skip_error_fields(
                EmailSkipReason.NO_ALLOWED_ATTACHMENT,
            )
            await self._persist_and_mark_seen(
                imap,
                uid,
                fields,
                processing_status=EmailProcessingStatus.SKIPPED,
                nat_intake_id=None,
                error_code=skip_code,
                error_message=skip_message,
            )
            return

        try:
            logger.info(
                'Calling NAT B2B: uid={} sender={} filename={} bytes={}',
                uid,
                parsed.sender_email,
                parsed.attachment.filename,
                len(parsed.attachment.content),
            )
            call_result = await self._nat_client.post_intake(
                filename=parsed.attachment.filename,
                content=parsed.attachment.content,
                sender_email=parsed.sender_email,
            )
        except NatIntakeTransportError as exc:
            if _should_retry_later(exc):
                logger.warning(
                    'NAT B2B transient failure; leaving uid={} unseen: {}',
                    uid,
                    exc,
                )
                return
            logger.error(
                'NAT B2B non-retriable failure for uid={}; marking skipped: {}',
                uid,
                exc,
            )
            skip_code, skip_message = _skip_error_fields(EmailSkipReason.NAT_B2B_FAILED)
            await self._persist_and_mark_seen(
                imap,
                uid,
                fields,
                processing_status=EmailProcessingStatus.SKIPPED,
                nat_intake_id=None,
                error_code=skip_code,
                error_message=skip_message,
            )
            return

        intake = call_result.response
        logger.info(
            'NAT B2B response: uid={} http_status={} intake_status={} intake_id={} '
            'error_code_present={}',
            uid,
            call_result.status_code,
            intake.status,
            intake.intake_id,
            intake.error_code is not None,
        )
        reply_status = await self._resolve_reply_status(intake=intake, fields=fields)
        if intake.status in {IntakeStatus.ACCEPTED, IntakeStatus.PARTIALLY_ACCEPTED}:
            await self._persist_and_mark_seen(
                imap,
                uid,
                fields,
                processing_status=EmailProcessingStatus.ACCEPTED,
                nat_intake_id=intake.intake_id,
                error_code=None,
                error_message=None,
                reply_status=reply_status,
            )
            return

        await self._persist_and_mark_seen(
            imap,
            uid,
            fields,
            processing_status=EmailProcessingStatus.REJECTED,
            nat_intake_id=intake.intake_id,
            error_code=intake.error_code.value if intake.error_code else None,
            error_message=intake.message,
            reply_status=reply_status,
        )

    async def _resolve_reply_status(
        self,
        *,
        intake: IntakeResponse,
        fields: _EmailAuditFields,
    ) -> EmailReplyStatus | None:
        if not settings.EMAIL_REPLY_ENABLED:
            return None
        if intake.status not in _INTAKE_STATUSES_REQUIRING_REPLY:
            return None
        return await self._reply_service.send_intake_reply(
            intake=intake,
            sender_email=fields.sender_email,
            original_subject=fields.subject,
            original_message_id=fields.message_id,
        )

    async def _is_duplicate(self, message_id: str) -> bool:
        async with SQLAlchemyUnitOfWork(db_manager.session_factory) as uow:
            return await uow.email_messages.exists_by_message_id(message_id)

    async def _persist_and_mark_seen(
        self,
        imap: ImapMailboxClient,
        uid: str,
        fields: _EmailAuditFields,
        *,
        processing_status: EmailProcessingStatus,
        nat_intake_id: UUID | None,
        error_code: str | None,
        error_message: str | None,
        reply_status: EmailReplyStatus | None = None,
    ) -> None:
        async with SQLAlchemyUnitOfWork(db_manager.session_factory) as uow:
            message = EmailMessage(
                id=uuid4(),
                message_id=fields.message_id,
                sender_email=normalize_email(fields.sender_email),
                subject=fields.subject,
                body=fields.body,
                received_at=fields.received_at,
                processing_status=processing_status.value,
                nat_intake_id=nat_intake_id,
                error_code=error_code,
                error_message=error_message,
                reply_status=reply_status.value if reply_status is not None else None,
            )
            await uow.email_messages.create(message)
            logger.info(
                'DB persist: uid={} message_id={} processing_status={} '
                'nat_intake_id={} error_code_present={} reply_status={}',
                uid,
                fields.message_id,
                processing_status.value,
                nat_intake_id,
                error_code is not None,
                reply_status.value if reply_status is not None else None,
            )
            await uow.commit()
            logger.info('DB commit ok: uid={} message_id={}', uid, fields.message_id)

        try:
            await imap.mark_seen(uid)
        except ImapClientError:
            logger.exception(
                'Persisted email message_id={} but failed to mark IMAP uid={} as seen',
                fields.message_id,
                uid,
            )
        else:
            logger.info(
                'IMAP processing finished: uid={} message_id={}',
                uid,
                fields.message_id,
            )


def _fields_from_parsed(parsed: ParsedIncomingEmail) -> _EmailAuditFields:
    return _EmailAuditFields(
        sender_email=parsed.sender_email,
        message_id=parsed.message_id,
        subject=parsed.subject,
        body=parsed.body,
        received_at=parsed.received_at,
    )


def _surrogate_message_id(uid: str) -> str:
    timestamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')
    return f'local-{uid}-{timestamp}'


def _skip_error_fields(reason: EmailSkipReason) -> tuple[str, str]:
    return reason.value, get_message(reason.value)


def _should_retry_later(exc: NatIntakeTransportError) -> bool:
    if exc.status_code is None:
        return True
    return exc.status_code >= 500
