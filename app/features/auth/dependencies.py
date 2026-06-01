from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi_keycloak_middleware import get_user
from pydantic import EmailStr

from app.features.auth.constants import AuthErrorCode
from app.features.auth.schemas import AuthErrorResponse, User
from app.features.nat.messages import get_message


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
