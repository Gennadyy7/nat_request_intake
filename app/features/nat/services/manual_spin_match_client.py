from dataclasses import dataclass
from types import TracebackType
from typing import Self
from uuid import UUID

import httpx

from app.core.client_credentials import (
    ClientCredentialsTokenError,
    ClientCredentialsTokenProvider,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.features.nat.schemas.manual_spin import MatchSpinRequest

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MatchSpinSuccess:
    pass


@dataclass(frozen=True, slots=True)
class MatchSpinFailure:
    message: str
    unavailable: bool


MatchSpinResult = MatchSpinSuccess | MatchSpinFailure


class MatchSpinClient:
    def __init__(
        self,
        token_provider: ClientCredentialsTokenProvider,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token_provider = token_provider
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient()
        self._url = settings.BATCH_MATCH_SPIN_URL
        self._timeout = float(settings.BATCH_NOTIFY_HTTP_TIMEOUT_SECONDS)

    async def match(self, batch_id: UUID) -> MatchSpinResult:
        try:
            token = await self._token_provider.get_access_token()
        except ClientCredentialsTokenError as exc:
            logger.error('Keycloak token request failed for manual SPIN: error={}', exc)
            return MatchSpinFailure(message=str(exc), unavailable=True)

        response = await self._post(batch_id=batch_id, access_token=token)
        if isinstance(response, MatchSpinFailure):
            return response

        if response.status_code == httpx.codes.UNAUTHORIZED:
            self._token_provider.invalidate()
            try:
                token = await self._token_provider.get_access_token()
            except ClientCredentialsTokenError as exc:
                logger.error(
                    'Keycloak token refresh failed for manual SPIN: error={}',
                    exc,
                )
                return MatchSpinFailure(message=str(exc), unavailable=True)
            response = await self._post(batch_id=batch_id, access_token=token)
            if isinstance(response, MatchSpinFailure):
                return response

        if response.status_code == httpx.codes.ACCEPTED:
            return MatchSpinSuccess()

        logger.warning(
            'MATCH_SPIN unexpected status: batch_id={} status={} body={}',
            batch_id,
            response.status_code,
            response.text,
        )
        return MatchSpinFailure(
            message=f'MATCH_SPIN returned HTTP {response.status_code}',
            unavailable=False,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
        await self._token_provider.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _post(
        self,
        *,
        batch_id: UUID,
        access_token: str,
    ) -> httpx.Response | MatchSpinFailure:
        payload = MatchSpinRequest(batch_id=batch_id)
        try:
            return await self._client.post(
                self._url,
                headers={'Authorization': f'Bearer {access_token}'},
                json=payload.model_dump(mode='json'),
                timeout=self._timeout,
            )
        except httpx.TimeoutException:
            logger.warning(
                'MATCH_SPIN timed out: batch_id={} timeout_seconds={}',
                batch_id,
                self._timeout,
            )
            return MatchSpinFailure(
                message=f'MATCH_SPIN timed out after {self._timeout}s',
                unavailable=True,
            )
        except httpx.HTTPError as exc:
            logger.warning(
                'MATCH_SPIN transport error: batch_id={} error={}',
                batch_id,
                exc,
            )
            return MatchSpinFailure(
                message='MATCH_SPIN transport error',
                unavailable=True,
            )
