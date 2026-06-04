from typing import Annotated

from fastapi import Depends, Form, HTTPException, status
from fastapi_keycloak_middleware import get_user
from pydantic import EmailStr, TypeAdapter, ValidationError

from app.core.config import settings
from app.features.auth.constants import AuthErrorCode
from app.features.auth.schemas import AuthErrorResponse, User
from app.features.auth.service_auth import is_email_poller_service_user
from app.features.email.schemas import normalize_email
from app.features.nat.messages import get_message

_email_adapter = TypeAdapter(EmailStr)


async def get_sender_email(
    user: Annotated[User, Depends(get_user)],
) -> EmailStr:
    if user.email is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=AuthErrorResponse(
                error_code=AuthErrorCode.MISSING_EMAIL,
                message=get_message(AuthErrorCode.MISSING_EMAIL),
            ).model_dump(mode='json'),
        )
    return user.email


async def require_email_poller_service(
    user: Annotated[User, Depends(get_user)],
) -> User:
    if is_email_poller_service_user(
        user,
        expected_client_id=settings.EMAIL_POLLER_CLIENT_ID,
    ):
        return user
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=AuthErrorResponse(
            error_code=AuthErrorCode.UNAUTHORIZED_SERVICE,
            message=get_message(AuthErrorCode.UNAUTHORIZED_SERVICE),
        ).model_dump(mode='json'),
    )


async def get_b2b_sender_email(
    sender_email: Annotated[str, Form()],
) -> EmailStr:
    try:
        return _email_adapter.validate_python(normalize_email(sender_email))
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=AuthErrorResponse(
                error_code=AuthErrorCode.INVALID_SENDER_EMAIL,
                message=get_message(AuthErrorCode.INVALID_SENDER_EMAIL),
            ).model_dump(mode='json'),
        ) from exc
