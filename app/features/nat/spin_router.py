from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from fastapi_keycloak_middleware import get_user
from pydantic import EmailStr

from app.features.auth.dependencies import get_sender_email
from app.features.auth.schemas import User
from app.features.nat.constants import ApiErrorCode
from app.features.nat.dependencies import (
    get_manual_spin_match_service,
    get_result_processing_query_service,
)
from app.features.nat.list_dependencies import (
    get_nat_result_processing_filters,
    get_nat_result_processing_sort_params,
    get_pagination_params,
)
from app.features.nat.messages import get_message
from app.features.nat.pagination import PaginationParams
from app.features.nat.query_params import NatResultProcessingFilters, SortParams
from app.features.nat.schemas.intake import IntakeResponse
from app.features.nat.schemas.manual_spin import ManualSpinMatchResponse
from app.features.nat.schemas.pagination import PaginatedResponse
from app.features.nat.schemas.result_processing import (
    NatResultProcessingDetail,
    NatResultProcessingListItem,
)
from app.features.nat.services.listing.result_processing_query_service import (
    ResultProcessingQueryService,
)
from app.features.nat.services.manual_spin_match_service import (
    ManualSpinAccepted,
    ManualSpinMatchService,
    ManualSpinRejected,
)

router = APIRouter(prefix='/spin', tags=['spin'])


@router.post(
    '/manual-match',
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ManualSpinMatchResponse,
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            'description': 'Uploaded file was rejected',
            'model': IntakeResponse,
        },
        status.HTTP_502_BAD_GATEWAY: {
            'description': 'SPIN service rejected the request',
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            'description': 'SPIN service or Keycloak is unavailable',
        },
    },
)
async def manual_spin_match(
    sender_email: Annotated[EmailStr, Depends(get_sender_email)],
    service: Annotated[
        ManualSpinMatchService,
        Depends(get_manual_spin_match_service),
    ],
    file: Annotated[UploadFile, File()],
) -> ManualSpinMatchResponse | JSONResponse:
    result = await service.process(
        filename=file.filename,
        content=await file.read(),
        sender_email=sender_email,
    )
    if isinstance(result, ManualSpinRejected):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=result.response.model_dump(mode='json'),
        )
    if isinstance(result, ManualSpinAccepted):
        return result.response

    error_code = (
        ApiErrorCode.MANUAL_SPIN_MATCH_UNAVAILABLE
        if result.unavailable
        else ApiErrorCode.MANUAL_SPIN_MATCH_FAILED
    )
    raise HTTPException(
        status_code=(
            status.HTTP_503_SERVICE_UNAVAILABLE
            if result.unavailable
            else status.HTTP_502_BAD_GATEWAY
        ),
        detail={
            'code': error_code,
            'message': get_message(error_code),
            'intake_id': str(result.intake_id),
            'batch_id': str(result.batch_id),
            'result_processing_id': str(result.result_processing_id),
        },
    )


@router.get(
    '/result-processing',
    response_model=PaginatedResponse[NatResultProcessingListItem],
)
async def list_result_processing(
    _user: Annotated[User, Depends(get_user)],
    query_service: Annotated[
        ResultProcessingQueryService,
        Depends(get_result_processing_query_service),
    ],
    filters: Annotated[
        NatResultProcessingFilters,
        Depends(get_nat_result_processing_filters),
    ],
    sort: Annotated[SortParams, Depends(get_nat_result_processing_sort_params)],
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
) -> PaginatedResponse[NatResultProcessingListItem]:
    return await query_service.list_result_processing(
        filters=filters,
        sort=sort,
        pagination=pagination,
    )


@router.get(
    '/result-processing/{result_processing_id}',
    response_model=NatResultProcessingDetail,
    responses={
        status.HTTP_404_NOT_FOUND: {
            'description': 'Result processing task not found',
        },
    },
)
async def get_result_processing(
    result_processing_id: UUID,
    _user: Annotated[User, Depends(get_user)],
    query_service: Annotated[
        ResultProcessingQueryService,
        Depends(get_result_processing_query_service),
    ],
) -> NatResultProcessingDetail:
    detail = await query_service.get_by_id(result_processing_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'code': ApiErrorCode.RESULT_PROCESSING_NOT_FOUND,
                'message': get_message(ApiErrorCode.RESULT_PROCESSING_NOT_FOUND),
                'result_processing_id': str(result_processing_id),
            },
        )
    return detail
