import time
from types import TracebackType
from typing import Self

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.logging import get_logger

logger = get_logger(__name__)

_TOKEN_REFRESH_SKEW_SECONDS = 30


class ClientCredentialsTokenError(Exception):
    pass


class _TokenResponse(BaseModel):
    access_token: str = Field(min_length=1)
    expires_in: float = Field(gt=0)


class ClientCredentialsTokenProvider:
    def __init__(
        self,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient()
        self._access_token: str | None = None
        self._expires_at_monotonic = 0.0

    async def get_access_token(self) -> str:
        if self._access_token is None or self._is_expired():
            await self._refresh()
        assert self._access_token is not None
        return self._access_token

    def invalidate(self) -> None:
        self._access_token = None
        self._expires_at_monotonic = 0.0

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    def _is_expired(self) -> bool:
        return (
            time.monotonic() >= self._expires_at_monotonic - _TOKEN_REFRESH_SKEW_SECONDS
        )

    async def _refresh(self) -> None:
        logger.info('Keycloak token request: client_id={}', self._client_id)
        try:
            response = await self._client.post(
                self._token_url,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self._client_id,
                    'client_secret': self._client_secret,
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
            )
        except httpx.HTTPError as exc:
            raise ClientCredentialsTokenError(
                'Keycloak token request failed',
            ) from exc

        if response.status_code != httpx.codes.OK:
            logger.error(
                'Keycloak token request failed: status={} body={}',
                response.status_code,
                response.text,
            )
            raise ClientCredentialsTokenError(
                f'Keycloak returned HTTP {response.status_code} for client credentials'
            )

        try:
            payload = _TokenResponse.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise ClientCredentialsTokenError(
                'Keycloak token response is invalid',
            ) from exc

        self._access_token = payload.access_token
        self._expires_at_monotonic = time.monotonic() + payload.expires_in
        logger.info(
            'Keycloak access token obtained: expires_in={}s', payload.expires_in
        )
