from typing import Annotated

from fastapi import Form, HTTPException, status

from app.features.nat.constants import ApiErrorCode
from app.features.nat.form_bool import parse_form_bool
from app.features.nat.messages import get_message


def get_single_stage_only(
    single_stage_only: Annotated[str | None, Form()] = None,
) -> bool:
    try:
        return parse_form_bool(single_stage_only, default=False)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                'code': ApiErrorCode.INVALID_SINGLE_STAGE_ONLY,
                'message': get_message(ApiErrorCode.INVALID_SINGLE_STAGE_ONLY),
            },
        ) from None
