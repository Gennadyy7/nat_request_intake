import httpx

from app.core.client_credentials import (
    ClientCredentialsTokenError,
    ClientCredentialsTokenProvider,
)
from nat_batch_notify_worker.app.core.config import settings

KeycloakTokenError = ClientCredentialsTokenError


class KeycloakTokenProvider(ClientCredentialsTokenProvider):
    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        super().__init__(
            token_url=self.token_url,
            client_id=settings.NAT_BATCH_NOTIFY_WORKER_KEYCLOAK_CLIENT_ID,
            client_secret=settings.NAT_BATCH_NOTIFY_WORKER_KEYCLOAK_CLIENT_SECRET,
            http_client=http_client,
        )

    @property
    def token_url(self) -> str:
        base = settings.KEYCLOAK_URL.rstrip('/')
        return f'{base}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token'
