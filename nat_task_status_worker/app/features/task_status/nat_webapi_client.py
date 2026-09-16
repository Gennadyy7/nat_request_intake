from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypeVar

import httpx
from pydantic import BaseModel

from app.features.nat.models import NatTask
from nat_task_status_worker.app.core.config import settings
from nat_task_status_worker.app.core.logging import get_logger
from nat_task_status_worker.app.features.task_status.errors.extraction import (
    extract_error_message,
)
from nat_task_status_worker.app.features.task_status.schemas import (
    NatSendResponse,
    NatStatusResponse,
)
from nat_task_status_worker.app.features.task_status.send_form_data import (
    build_send_form_data,
)

if TYPE_CHECKING:
    from types import TracebackType

logger = get_logger(__name__)

NatWebApiAction = Literal['send', 'status']
TResponse = TypeVar('TResponse', bound=BaseModel)


@dataclass(frozen=True, slots=True)
class NatWebApiSuccess[T]:
    payload: T


@dataclass(frozen=True, slots=True)
class NatWebApiTransientError:
    message: str


@dataclass(frozen=True, slots=True)
class NatWebApiPermanentError:
    message: str
    http_status: int


NatSendResult = (
    NatWebApiSuccess[NatSendResponse]
    | NatWebApiTransientError
    | NatWebApiPermanentError
)
NatStatusResult = (
    NatWebApiSuccess[NatStatusResponse]
    | NatWebApiTransientError
    | NatWebApiPermanentError
)


class NatWebApiClient:
    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient()
        self._timeout = float(settings.NAT_WEBAPI_HTTP_TIMEOUT_SECONDS)

    async def send_task(self, task: NatTask) -> NatSendResult:
        form_data = build_send_form_data(task)
        return await self._post('send', form_data, NatSendResponse)

    async def get_task_status(self, nat_request_id: int) -> NatStatusResult:
        form_data = {
            'ACTION': 'status',
            'user': settings.NAT_USER,
            'psw': settings.NAT_PASSWORD,
            'id': str(nat_request_id),
        }
        return await self._post('status', form_data, NatStatusResponse)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> NatWebApiClient:
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
        action: NatWebApiAction,
        form_data: dict[str, str],
        response_model: type[TResponse],
    ) -> (
        NatWebApiSuccess[TResponse] | NatWebApiTransientError | NatWebApiPermanentError
    ):
        try:
            response = await self._client.post(
                settings.NAT_WEBAPI_URL,
                data=form_data,
                timeout=self._timeout,
            )
        except httpx.TimeoutException:
            logger.warning('NAT webapi timeout: action={}', action)
            return NatWebApiTransientError(
                message=f'NAT webapi request timed out after {self._timeout}s',
            )
        except httpx.HTTPError as exc:
            logger.warning(
                'NAT webapi transport error: action={} error={}', action, exc
            )
            return NatWebApiTransientError(message='NAT webapi transport error')

        if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
            return NatWebApiTransientError(
                message=f'NAT webapi returned HTTP {response.status_code}',
            )
        if response.status_code >= 500:
            return NatWebApiTransientError(
                message=f'NAT webapi returned HTTP {response.status_code}',
            )
        if response.status_code >= 400:
            return NatWebApiPermanentError(
                message=extract_error_message(
                    response.text,
                    http_status=response.status_code,
                    action=action,
                ),
                http_status=response.status_code,
            )

        try:
            payload = response_model.model_validate_json(response.content)
        except Exception as exc:
            logger.warning(
                'NAT webapi invalid JSON: action={} body={}',
                action,
                response.text,
            )
            return NatWebApiTransientError(
                message=f'NAT webapi returned invalid JSON: {exc}',
            )

        return NatWebApiSuccess(payload=payload)
