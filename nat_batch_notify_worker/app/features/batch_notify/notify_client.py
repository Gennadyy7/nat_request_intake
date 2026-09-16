from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import httpx

from nat_batch_notify_worker.app.core.config import settings
from nat_batch_notify_worker.app.core.keycloak_token import (
    KeycloakTokenError,
    KeycloakTokenProvider,
)
from nat_batch_notify_worker.app.core.logging import get_logger
from nat_batch_notify_worker.app.features.batch_notify.schemas import NotifyBatchRequest

if TYPE_CHECKING:
    from types import TracebackType

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class BatchNotifySuccess:
    pass


@dataclass(frozen=True, slots=True)
class BatchNotifyFailure:
    message: str


BatchNotifyResult = BatchNotifySuccess | BatchNotifyFailure


class BatchNotifyClient:
    def __init__(
        self,
        token_provider: KeycloakTokenProvider,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token_provider = token_provider
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient()
        self._notify_url = settings.BATCH_NOTIFY_URL
        self._timeout = float(settings.BATCH_NOTIFY_HTTP_TIMEOUT_SECONDS)

    async def notify(self, batch_id: UUID) -> BatchNotifyResult:
        try:
            token = await self._token_provider.get_access_token()
        except KeycloakTokenError as exc:
            logger.error(
                'Keycloak token request failed for batch notify: error={}', exc
            )
            return BatchNotifyFailure(message=str(exc))

        try:
            response = await self._post_json(batch_id=batch_id, access_token=token)
        except BatchNotifyTransportError as exc:
            return BatchNotifyFailure(message=str(exc))

        if response.status_code == httpx.codes.UNAUTHORIZED:
            logger.warning(
                'BATCH_NOTIFY returned 401; refreshing Keycloak token and retrying once'
            )
            self._token_provider.invalidate()
            try:
                token = await self._token_provider.get_access_token()
            except KeycloakTokenError as exc:
                logger.error(
                    'Keycloak token refresh failed for batch notify: error={}', exc
                )
                return BatchNotifyFailure(message=str(exc))
            try:
                response = await self._post_json(batch_id=batch_id, access_token=token)
            except BatchNotifyTransportError as exc:
                return BatchNotifyFailure(message=str(exc))

        if response.status_code == httpx.codes.ACCEPTED:
            return BatchNotifySuccess()

        logger.warning(
            'BATCH_NOTIFY unexpected status: batch_id={} status={} body={}',
            batch_id,
            response.status_code,
            response.text,
        )
        return BatchNotifyFailure(
            message=f'BATCH_NOTIFY returned HTTP {response.status_code}',
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> BatchNotifyClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _post_json(self, *, batch_id: UUID, access_token: str) -> httpx.Response:
        payload = NotifyBatchRequest(batch_id=batch_id)
        try:
            return await self._client.post(
                self._notify_url,
                headers={'Authorization': f'Bearer {access_token}'},
                json=payload.model_dump(mode='json'),
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            logger.warning(
                'BATCH_NOTIFY request timed out: batch_id={} timeout_seconds={}',
                batch_id,
                self._timeout,
            )
            raise BatchNotifyTransportError(
                f'BATCH_NOTIFY request timed out after {self._timeout}s',
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning(
                'BATCH_NOTIFY transport error: batch_id={} error={}',
                batch_id,
                exc,
            )
            raise BatchNotifyTransportError('BATCH_NOTIFY transport error') from exc


class BatchNotifyTransportError(Exception):
    pass
