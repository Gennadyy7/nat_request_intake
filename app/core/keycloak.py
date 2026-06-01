from fastapi_keycloak_middleware import KeycloakConfiguration

from app.core.config import settings
from app.features.auth.schemas import User


def get_keycloak_config() -> KeycloakConfiguration:
    return KeycloakConfiguration(
        url=settings.KEYCLOAK_URL,
        realm=settings.KEYCLOAK_REALM,
        client_id=settings.KEYCLOAK_CLIENT_ID,
        client_secret=settings.KEYCLOAK_CLIENT_SECRET,
        swagger_client_id=settings.KEYCLOAK_SWAGGER_CLIENT_ID,
        claims=[
            'sub',
            'name',
            'email',
            'preferred_username',
            'given_name',
            'family_name',
            'roles',
        ],
        reject_on_missing_claim=False,
    )


async def map_user(userinfo: dict[str, object]) -> User:
    return User.from_claims(userinfo)
