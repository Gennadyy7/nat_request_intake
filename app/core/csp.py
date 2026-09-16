from collections.abc import Iterable
from urllib.parse import urlsplit

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CSP_API_POLICY = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"

_DOCS_UI_PATHS = frozenset(
    {
        '/docs',
        '/docs/oauth2-redirect',
        '/redoc',
    }
)

_DOCS_POLICY_BASE = (
    "default-src 'none'; "
    "script-src 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    'img-src data: https://fastapi.tiangolo.com; '
    'font-src https://fonts.gstatic.com; '
    'worker-src blob:; '
    "frame-ancestors 'none'; "
    "base-uri 'none'"
)


def origin_from_url(url: str) -> str | None:
    """Return scheme://netloc for an absolute URL, or None if incomplete."""
    parsed = urlsplit(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return None
    return f'{parsed.scheme}://{parsed.netloc}'


def collect_keycloak_origins(*urls: str) -> tuple[str, ...]:
    origins: list[str] = []
    seen: set[str] = set()
    for url in urls:
        origin = origin_from_url(url)
        if origin is None or origin in seen:
            continue
        seen.add(origin)
        origins.append(origin)
    return tuple(origins)


def build_docs_csp_policy(keycloak_origins: Iterable[str]) -> str:
    origins = tuple(origin for origin in keycloak_origins if origin)
    connect_src = "connect-src 'self'"
    frame_src = 'frame-src'
    form_action = "form-action 'self'"
    if origins:
        joined = ' '.join(origins)
        connect_src = f'{connect_src} {joined}'
        frame_src = f'{frame_src} {joined}'
        form_action = f'{form_action} {joined}'
    else:
        frame_src = f"{frame_src} 'none'"

    return f'{_DOCS_POLICY_BASE}; {connect_src}; {frame_src}; {form_action}'


def is_docs_ui_path(path: str) -> bool:
    return path in _DOCS_UI_PATHS


class ContentSecurityPolicyMiddleware:
    """ASGI middleware that attaches Content-Security-Policy to HTTP responses."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        enabled: bool,
        docs_enabled: bool,
        api_policy: str,
        docs_policy: str,
    ) -> None:
        self.app = app
        self.enabled = enabled
        self.docs_enabled = docs_enabled
        self.api_policy = api_policy
        self.docs_policy = docs_policy

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http' or not self.enabled:
            await self.app(scope, receive, send)
            return

        path = scope.get('path', '')
        use_docs_policy = self.docs_enabled and is_docs_ui_path(path)
        policy = self.docs_policy if use_docs_policy else self.api_policy

        async def send_with_csp(message: Message) -> None:
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(scope=message)
                headers['Content-Security-Policy'] = policy
            await send(message)

        await self.app(scope, receive, send_with_csp)
