from typing import Self, cast

from pydantic import BaseModel, EmailStr

from app.features.auth.constants import AuthErrorCode


class AuthErrorResponse(BaseModel):
    code: AuthErrorCode
    message: str


class User(BaseModel):
    id: str
    username: str | None = None
    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    roles: list[str] = []
    authorized_party: str | None = None

    @classmethod
    def from_claims(cls, claims: dict[str, object]) -> Self:
        azp = claims.get('azp')
        client_id = claims.get('client_id')
        authorized_party = azp if azp is not None else client_id
        return cls(
            id=cast(str, claims.get('sub', '')),
            username=cast(str | None, claims.get('preferred_username')),
            email=cast(EmailStr | None, claims.get('email')),
            first_name=cast(str | None, claims.get('given_name')),
            last_name=cast(str | None, claims.get('family_name')),
            full_name=cast(str | None, claims.get('name')),
            roles=cast(list[str], claims.get('roles', [])),
            authorized_party=cast(str | None, authorized_party),
        )
