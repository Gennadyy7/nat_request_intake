from __future__ import annotations

import time
from typing import TYPE_CHECKING

import httpx

from email_poller.app.core.config import settings
from email_poller.app.core.logging import get_logger

if TYPE_CHECKING:
    from types import TracebackType

logger = get_logger(__name__)

_TOKEN_REFRESH_SKEW_SECONDS = 30


class KeycloakTokenError(Exception):
    pass


class KeycloakTokenProvider:
    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient()
        self._access_token: str | None = None
        self._expires_at_monotonic: float = 0.0

    @property
    def token_url(self) -> str:
        base = settings.KEYCLOAK_URL.rstrip('/')
        return f'{base}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token'

    async def get_access_token(self) -> str:
        if self._access_token is not None and not self._is_expired():
            return self._access_token
        await self._refresh()
        assert self._access_token is not None
        return self._access_token

    def invalidate(self) -> None:
        self._access_token = None
        self._expires_at_monotonic = 0.0

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> KeycloakTokenProvider:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    def _is_expired(self) -> bool:
        if self._access_token is None:
            return True
        return (
            time.monotonic() >= self._expires_at_monotonic - _TOKEN_REFRESH_SKEW_SECONDS
        )

    async def _refresh(self) -> None:
        logger.info(
            'Keycloak token request: client_id={}',
            settings.EMAIL_POLLER_KEYCLOAK_CLIENT_ID,
        )
        response = await self._client.post(
            self.token_url,
            data={
                'grant_type': 'client_credentials',
                'client_id': settings.EMAIL_POLLER_KEYCLOAK_CLIENT_ID,
                'client_secret': settings.EMAIL_POLLER_KEYCLOAK_CLIENT_SECRET,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
        if response.status_code != httpx.codes.OK:
            logger.error(
                'Keycloak token request failed: status={} body={}',
                response.status_code,
                response.text,
            )
            raise KeycloakTokenError(
                f'Keycloak returned HTTP {response.status_code} for client credentials'
            )

        payload = response.json()
        access_token = payload.get('access_token')
        expires_in = payload.get('expires_in')
        if not isinstance(access_token, str) or not access_token:
            raise KeycloakTokenError('Keycloak token response missing access_token')
        if not isinstance(expires_in, (int, float)) or expires_in <= 0:
            raise KeycloakTokenError('Keycloak token response missing expires_in')

        self._access_token = access_token
        self._expires_at_monotonic = time.monotonic() + float(expires_in)
        logger.info('Keycloak access token obtained: expires_in={}s', int(expires_in))
