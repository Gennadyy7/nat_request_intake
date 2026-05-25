from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse
from fastapi_keycloak_middleware import get_user
from pydantic import EmailStr

from app.features.auth.schemas import User
from app.features.nat.constants import IntakeStatus
from app.features.nat.schemas.intake import IntakeResponse
from app.features.nat.services.intake_service import intake_service

router = APIRouter(prefix='/nat', tags=['nat'])


@router.post(
    '/intake',
    response_model=IntakeResponse,
    responses={422: {'model': IntakeResponse}},
)
async def intake_file(
    _user: Annotated[User, Depends(get_user)],
    file: Annotated[UploadFile, File()],
    sender_email: Annotated[EmailStr, Form()],
) -> IntakeResponse | JSONResponse:
    content = await file.read()
    result = await intake_service.validate(
        filename=file.filename,
        content=content,
        sender_email=sender_email,
    )
    if result.status == IntakeStatus.REJECTED:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=result.model_dump(mode='json'),
        )
    return result
