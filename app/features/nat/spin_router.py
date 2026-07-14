from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_keycloak_middleware import get_user

from app.features.auth.schemas import User
from app.features.nat.constants import ApiErrorCode
from app.features.nat.dependencies import get_result_processing_query_service
from app.features.nat.list_dependencies import (
    get_nat_result_processing_filters,
    get_nat_result_processing_sort_params,
    get_pagination_params,
)
from app.features.nat.messages import get_message
from app.features.nat.pagination import PaginationParams
from app.features.nat.query_params import NatResultProcessingFilters, SortParams
from app.features.nat.schemas.pagination import PaginatedResponse
from app.features.nat.schemas.result_processing import (
    NatResultProcessingDetail,
    NatResultProcessingListItem,
)
from app.features.nat.services.listing.result_processing_query_service import (
    ResultProcessingQueryService,
)

router = APIRouter(prefix='/spin', tags=['spin'])


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
