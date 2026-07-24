from fastapi.responses import JSONResponse
from pydantic import EmailStr
from starlette import status

from app.features.nat.constants import IntakeStatus
from app.features.nat.schemas.intake import IntakeResponse
from app.features.nat.services.intake.intake_service import IntakeService


async def process_intake_upload(
    *,
    service: IntakeService,
    filename: str | None,
    content: bytes,
    sender_email: EmailStr,
    enforce_max_date_range: bool,
    enforce_past_date_range: bool,
) -> IntakeResponse | JSONResponse:
    result = await service.process(
        filename=filename,
        content=content,
        sender_email=sender_email,
        enforce_max_date_range=enforce_max_date_range,
        enforce_past_date_range=enforce_past_date_range,
    )
    if result.status == IntakeStatus.REJECTED:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=result.model_dump(mode='json'),
        )
    return result
