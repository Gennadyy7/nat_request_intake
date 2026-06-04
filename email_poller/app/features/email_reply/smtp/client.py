from __future__ import annotations

import asyncio
from email.message import EmailMessage
from typing import TYPE_CHECKING

import aiosmtplib
from aiosmtplib.errors import SMTPException

from email_poller.app.core.config import settings
from email_poller.app.core.logging import get_logger

if TYPE_CHECKING:
    from types import TracebackType

logger = get_logger(__name__)


class SmtpClientError(Exception):
    pass


class SmtpMailClient:
    def __init__(self) -> None:
        self._client: aiosmtplib.SMTP | None = None

    async def __aenter__(self) -> SmtpMailClient:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        if self._client is not None:
            return

        use_tls = settings.SMTP_USE_SSL
        start_tls = not use_tls
        client = aiosmtplib.SMTP(
            hostname=settings.IMAP_SERVER,
            port=settings.SMTP_PORT,
            username=settings.IMAP_USER,
            password=settings.IMAP_PASSWORD,
            use_tls=use_tls,
            start_tls=start_tls,
            timeout=float(settings.IMAP_TIMEOUT_SECONDS),
        )

        try:
            await client.connect()
        except (SMTPException, OSError, TimeoutError) as exc:
            raise SmtpClientError(
                'SMTP connect failed: '
                f'server={settings.IMAP_SERVER} '
                f'port={settings.SMTP_PORT} '
                f'use_ssl={settings.SMTP_USE_SSL} '
                f'timeout_seconds={settings.IMAP_TIMEOUT_SECONDS}'
            ) from exc

        self._client = client
        logger.info(
            'SMTP connected: server={} port={} use_ssl={}',
            settings.IMAP_SERVER,
            settings.SMTP_PORT,
            settings.SMTP_USE_SSL,
        )

    async def disconnect(self) -> None:
        if self._client is None:
            return
        try:
            await self._client.quit()
        except (SMTPException, OSError, asyncio.CancelledError) as exc:
            logger.warning('SMTP quit failed: {}', exc)
        finally:
            self._client = None

    async def send_message(self, message: EmailMessage) -> None:
        client = self._require_client()
        try:
            await client.send_message(message)
        except SMTPException as exc:
            raise SmtpClientError(f'SMTP send failed: {exc}') from exc
        logger.info(
            'SMTP message sent: subject={!r} recipients={}',
            message.get('Subject'),
            message.get('To'),
        )

    def _require_client(self) -> aiosmtplib.SMTP:
        if self._client is None:
            raise SmtpClientError('SMTP client is not connected')
        return self._client
