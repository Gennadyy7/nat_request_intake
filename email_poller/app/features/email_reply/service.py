from app.features.email.constants import EmailReplyStatus
from app.features.nat.schemas.intake import IntakeResponse
from email_poller.app.core.logging import get_logger
from email_poller.app.features.email_reply.composer import build_intake_reply_message
from email_poller.app.features.email_reply.smtp.client import (
    SmtpClientError,
    SmtpMailClient,
)

logger = get_logger(__name__)


class EmailReplyService:
    async def send_intake_reply(
        self,
        *,
        intake: IntakeResponse,
        sender_email: str,
        original_subject: str | None,
        original_message_id: str,
    ) -> EmailReplyStatus:
        mime_message = build_intake_reply_message(
            intake=intake,
            sender_email=sender_email,
            original_subject=original_subject,
            original_message_id=original_message_id,
        )
        logger.info(
            'Sending intake reply: intake_id={} status={} recipient={} subject={!r}',
            intake.intake_id,
            intake.status.value,
            sender_email,
            mime_message.get('Subject'),
        )
        try:
            async with SmtpMailClient() as smtp:
                await smtp.send_message(mime_message)
        except SmtpClientError:
            logger.exception(
                'Failed to send intake reply: intake_id={} recipient={}',
                intake.intake_id,
                sender_email,
            )
            return EmailReplyStatus.FAILED

        logger.info(
            'Intake reply sent: intake_id={} recipient={}',
            intake.intake_id,
            sender_email,
        )
        return EmailReplyStatus.SENT
