from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from app.features.nat.schemas.intake import IntakeResponse
from email_poller.app.core.config import settings
from email_poller.app.core.keycloak_token import KeycloakTokenProvider
from email_poller.app.core.logging import get_logger

if TYPE_CHECKING:
    from types import TracebackType

logger = get_logger(__name__)


class NatIntakeTransportError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class NatIntakeCallResult:
    status_code: int
    response: IntakeResponse


class NatIntakeClient:
    def __init__(
        self,
        token_provider: KeycloakTokenProvider,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token_provider = token_provider
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient()
        self._b2b_url = settings.NAT_INTAKE_B2B_URL
        self._timeout = float(settings.NAT_INTAKE_HTTP_TIMEOUT_SECONDS)

    async def post_intake(
        self,
        *,
        filename: str,
        content: bytes,
        sender_email: str,
    ) -> NatIntakeCallResult:
        token = await self._token_provider.get_access_token()
        response = await self._post_multipart(
            access_token=token,
            filename=filename,
            content=content,
            sender_email=sender_email,
        )

        if response.status_code == httpx.codes.UNAUTHORIZED:
            logger.warning(
                'NAT B2B returned 401; refreshing Keycloak token and retrying once'
            )
            self._token_provider.invalidate()
            token = await self._token_provider.get_access_token()
            response = await self._post_multipart(
                access_token=token,
                filename=filename,
                content=content,
                sender_email=sender_email,
            )

        return self._parse_response(response)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> NatIntakeClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _post_multipart(
        self,
        *,
        access_token: str,
        filename: str,
        content: bytes,
        sender_email: str,
    ) -> httpx.Response:
        try:
            return await self._client.post(
                self._b2b_url,
                headers={'Authorization': f'Bearer {access_token}'},
                data={'sender_email': sender_email},
                files={'file': (filename, content)},
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            logger.error(
                'NAT B2B request timed out: url={} timeout_seconds={}',
                self._b2b_url,
                self._timeout,
            )
            raise NatIntakeTransportError(
                f'NAT B2B request timed out after {self._timeout}s',
            ) from exc
        except httpx.HTTPError as exc:
            logger.error('NAT B2B request failed: url={} error={}', self._b2b_url, exc)
            raise NatIntakeTransportError('NAT B2B request failed') from exc

    def _parse_response(self, response: httpx.Response) -> NatIntakeCallResult:
        if response.status_code in {httpx.codes.OK, httpx.codes.UNPROCESSABLE_ENTITY}:
            try:
                intake_response = IntakeResponse.model_validate_json(response.content)
            except Exception as exc:
                logger.error(
                    'Failed to parse NAT B2B response: status={} body={}',
                    response.status_code,
                    response.text,
                )
                raise NatIntakeTransportError(
                    'NAT B2B returned an invalid intake response body',
                    status_code=response.status_code,
                ) from exc
            return NatIntakeCallResult(
                status_code=response.status_code,
                response=intake_response,
            )

        logger.error(
            'NAT B2B unexpected status: status={} body={}',
            response.status_code,
            response.text,
        )
        raise NatIntakeTransportError(
            f'NAT B2B returned HTTP {response.status_code}',
            status_code=response.status_code,
        )
