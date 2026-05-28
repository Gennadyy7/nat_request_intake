from typing import Self, cast

from pydantic import BaseModel, EmailStr

from app.features.auth.constants import AuthErrorCode


class AuthErrorResponse(BaseModel):
    error_code: AuthErrorCode


class User(BaseModel):
    id: str
    username: str | None = None
    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    roles: list[str] = []

    @classmethod
    def from_claims(cls, claims: dict[str, object]) -> Self:
        return cls(
            id=cast(str, claims.get('sub', '')),
            username=cast(str | None, claims.get('preferred_username')),
            email=cast(EmailStr | None, claims.get('email')),
            first_name=cast(str | None, claims.get('given_name')),
            last_name=cast(str | None, claims.get('family_name')),
            full_name=cast(str | None, claims.get('name')),
            roles=cast(list[str], claims.get('roles', [])),
        )
