from dataclasses import dataclass
from types import TracebackType
from typing import Self

import httpx

from assomi_worker.app.core.config import settings
from assomi_worker.app.core.logging import get_logger
from assomi_worker.app.features.assomi.code_msg import CodeMsgSequence
from assomi_worker.app.features.assomi.response_parsing import (
    AssomiAbonent,
    AssomiAbonentInfo,
    AssomiBusinessError,
    is_code_msg_taken_error,
    parse_assomi_response,
)
from assomi_worker.app.features.assomi.xml_payload import build_assomi_xml_payload

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AssomiSuccess:
    abonents: tuple[AssomiAbonent, ...]
    code_msg_used: int
    code_msg_retries: int


@dataclass(frozen=True, slots=True)
class AssomiTransientError:
    message: str


@dataclass(frozen=True, slots=True)
class AssomiPermanentError:
    message: str


AssomiFetchResult = AssomiSuccess | AssomiTransientError | AssomiPermanentError


class AssomiClient:
    def __init__(
        self,
        code_msg_sequence: CodeMsgSequence,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._code_msg_sequence = code_msg_sequence
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient()
        self._timeout = float(settings.ASSOMI_HTTP_TIMEOUT_SECONDS)

    async def fetch_abonents(self, local_parts: list[str]) -> AssomiFetchResult:
        if not local_parts:
            return AssomiSuccess(abonents=(), code_msg_used=0, code_msg_retries=0)

        branch = settings.ASSOMI_BRANCH
        system = settings.ASSOMI_SYSTEM
        name = settings.ASSOMI_NAME
        range_size = self._code_msg_sequence.range_size()
        first_code: int | None = None
        retries = 0

        for _attempt in range(range_size):
            code_msg = self._code_msg_sequence.peek(
                branch=branch,
                system=system,
                name=name,
            )
            if first_code is None:
                first_code = code_msg
            elif code_msg == first_code and retries > 0:
                return AssomiTransientError(
                    message=(
                        'ASSOMI code_msg range exhausted: all values appear taken '
                        f'[{settings.ASSOMI_CODE_MSG_MIN}..{settings.ASSOMI_CODE_MSG_MAX}]'
                    ),
                )

            xml_payload = build_assomi_xml_payload(
                logins=local_parts,
                branch=branch,
                system=system,
                code_msg=code_msg,
                name=name,
                is_test=settings.ASSOMI_IS_TEST,
                systime_timezone=settings.ASSOMI_SYSTIME_TIMEZONE,
                systime_format=settings.ASSOMI_SYSTIME_FORMAT,
            )
            transport_result = await self._post_xml(xml_payload)
            if isinstance(
                transport_result, AssomiTransientError | AssomiPermanentError
            ):
                return transport_result

            try:
                parsed = parse_assomi_response(transport_result)
            except ValueError as exc:
                return AssomiPermanentError(message=str(exc))

            if isinstance(parsed, AssomiBusinessError):
                if is_code_msg_taken_error(parsed):
                    logger.warning(
                        'ASSOMI code_msg taken: code_msg={} message={}',
                        code_msg,
                        parsed.error_message,
                    )
                    self._code_msg_sequence.advance(
                        branch=branch,
                        system=system,
                        name=name,
                    )
                    retries += 1
                    continue
                return AssomiPermanentError(
                    message=(
                        f'ASSOMI business error: code={parsed.error_code} '
                        f'message={parsed.error_message}'
                    ),
                )

            if isinstance(parsed, AssomiAbonentInfo):
                self._code_msg_sequence.mark_used_and_advance(
                    branch=branch,
                    system=system,
                    name=name,
                )
                return AssomiSuccess(
                    abonents=parsed.abonents,
                    code_msg_used=code_msg,
                    code_msg_retries=retries,
                )

        return AssomiTransientError(
            message=(
                'ASSOMI code_msg range exhausted: all values appear taken '
                f'[{settings.ASSOMI_CODE_MSG_MIN}..{settings.ASSOMI_CODE_MSG_MAX}]'
            ),
        )

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

    async def _post_xml(
        self,
        xml_payload: str,
    ) -> str | AssomiTransientError | AssomiPermanentError:
        try:
            response = await self._client.post(
                settings.ASSOMI_URL,
                content=xml_payload.encode('utf-8'),
                headers={'Content-Type': 'application/xml; charset=utf-8'},
                timeout=self._timeout,
            )
        except httpx.TimeoutException:
            logger.warning('ASSOMI request timed out after {}s', self._timeout)
            return AssomiTransientError(
                message=f'ASSOMI request timed out after {self._timeout}s',
            )
        except httpx.HTTPError as exc:
            logger.warning('ASSOMI transport error: {}', exc)
            return AssomiTransientError(message='ASSOMI transport error')

        if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
            return AssomiTransientError(
                message=f'ASSOMI returned HTTP {response.status_code}',
            )
        if response.status_code >= 500:
            return AssomiTransientError(
                message=f'ASSOMI returned HTTP {response.status_code}',
            )
        if response.status_code >= 400:
            return AssomiPermanentError(
                message=f'ASSOMI returned HTTP {response.status_code}',
            )

        return response.text
