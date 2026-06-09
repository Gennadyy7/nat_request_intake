from __future__ import annotations

import asyncio
import ssl
from typing import TYPE_CHECKING

import aioimaplib
from aioimaplib import Response
from aioimaplib.aioimaplib import Abort, AioImapException

from email_poller.app.core.config import settings
from email_poller.app.core.logging import get_logger

if TYPE_CHECKING:
    from types import TracebackType

logger = get_logger(__name__)


class ImapClientError(Exception):
    pass


class ImapMailboxClient:
    def __init__(self) -> None:
        self._client: aioimaplib.IMAP4 | aioimaplib.IMAP4_SSL | None = None

    async def __aenter__(self) -> ImapMailboxClient:
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

        try:
            if settings.IMAP_USE_SSL:
                ssl_context = ssl.create_default_context()
                client: aioimaplib.IMAP4 | aioimaplib.IMAP4_SSL = aioimaplib.IMAP4_SSL(
                    host=settings.IMAP_SERVER,
                    port=settings.IMAP_PORT,
                    ssl_context=ssl_context,
                )
            else:
                client = aioimaplib.IMAP4(
                    host=settings.IMAP_SERVER,
                    port=settings.IMAP_PORT,
                )

            client.timeout = float(settings.IMAP_TIMEOUT_SECONDS)
            await client.wait_hello_from_server()
        except TimeoutError as exc:
            raise ImapClientError(
                'IMAP hello timeout: '
                f'server={settings.IMAP_SERVER} '
                f'port={settings.IMAP_PORT} '
                f'use_ssl={settings.IMAP_USE_SSL} '
                f'timeout_seconds={settings.IMAP_TIMEOUT_SECONDS}'
            ) from exc

        login_response = await client.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
        self._check_response(login_response, operation='login')

        select_response = await client.select(settings.IMAP_MAILBOX)
        self._check_response(select_response, operation='select')
        self._client = client
        logger.info(
            'IMAP connected: server={} port={} use_ssl={} mailbox={}',
            settings.IMAP_SERVER,
            settings.IMAP_PORT,
            settings.IMAP_USE_SSL,
            settings.IMAP_MAILBOX,
        )

    async def disconnect(self) -> None:
        if self._client is None:
            return
        try:
            await self._client.logout()
        except (Abort, AioImapException, asyncio.CancelledError) as exc:
            logger.warning('IMAP logout failed: {}', exc)
        finally:
            self._client = None

    async def list_unseen_uids(self) -> list[str]:
        client = self._require_client()
        response = await client.uid_search('UNSEEN', charset=None)
        self._check_response(response, operation='UID SEARCH UNSEEN')
        if not response.lines:
            logger.debug('IMAP UID SEARCH UNSEEN: empty response')
            return []
        raw_line = response.lines[0]
        if not isinstance(raw_line, (bytes, bytearray)):
            logger.warning(
                'IMAP UID SEARCH UNSEEN: unexpected response line type: {}',
                type(raw_line),
            )
            return []
        uid_bytes = bytes(raw_line).strip()
        if not uid_bytes:
            logger.debug('IMAP UID SEARCH UNSEEN: no uids in first line')
            return []
        uids = [uid.decode() for uid in uid_bytes.split() if uid]
        logger.info('IMAP UID SEARCH UNSEEN: found {} uid(s)', len(uids))
        logger.debug('IMAP UID SEARCH UNSEEN: uids={}', uids[:50])
        return uids

    async def fetch_header_fields_peek(self, uid: str) -> bytes:
        client = self._require_client()
        logger.debug('IMAP UID FETCH header fields: uid={}', uid)
        response = await client.uid(
            'FETCH',
            uid,
            '(BODY.PEEK[HEADER.FIELDS (FROM MESSAGE-ID DATE)])',
        )
        self._check_response(
            response,
            operation=f'UID FETCH header fields uid={uid}',
        )
        payload = _extract_fetch_payload(response)
        if not payload:
            raise ImapClientError(f'Empty header FETCH payload for uid={uid}')
        logger.debug('IMAP UID FETCH header fields: uid={} bytes={}', uid, len(payload))
        return payload

    async def fetch_rfc822(self, uid: str) -> bytes:
        client = self._require_client()
        logger.debug('IMAP UID FETCH: uid={}', uid)
        response = await client.uid('FETCH', uid, 'BODY.PEEK[]')
        self._check_response(response, operation=f'UID FETCH uid={uid}')
        payload = _extract_fetch_payload(response)
        if not payload:
            raise ImapClientError(f'Empty FETCH payload for uid={uid}')
        logger.debug('IMAP UID FETCH: uid={} bytes={}', uid, len(payload))
        return payload

    async def mark_seen(self, uid: str) -> None:
        client = self._require_client()
        logger.debug('IMAP UID STORE: mark seen uid={}', uid)
        response = await client.uid('STORE', uid, '+FLAGS', '\\Seen')
        self._check_response(response, operation=f'UID STORE mark seen uid={uid}')
        logger.info('IMAP marked seen: uid={}', uid)

    def _require_client(self) -> aioimaplib.IMAP4 | aioimaplib.IMAP4_SSL:
        if self._client is None:
            raise ImapClientError('IMAP client is not connected')
        return self._client

    def _check_response(self, response: Response, *, operation: str) -> None:
        if response.result != 'OK':
            detail = _format_response_lines(response)
            raise ImapClientError(f'IMAP {operation} failed: {detail}')


def _extract_fetch_payload(response: Response) -> bytes:
    chunks: list[bytes] = []
    for line in response.lines:
        if isinstance(line, bytearray):
            chunks.append(bytes(line))
            continue
        if not isinstance(line, bytes):
            continue
        if b'FETCH' in line and (b'BODY' in line or b'RFC822' in line):
            continue
        if line in {b')', b''}:
            continue
        chunks.append(line)
    return b''.join(chunks)


def _format_response_lines(response: Response) -> str:
    parts: list[str] = []
    for line in response.lines[:5]:
        if isinstance(line, (bytes, bytearray)):
            text = bytes(line).decode('utf-8', errors='replace')
            if len(text) > 200:
                text = f'{text[:200]}...'
            parts.append(text)
    return '; '.join(parts) if parts else response.result
