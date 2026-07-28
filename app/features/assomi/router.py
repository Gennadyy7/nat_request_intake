from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from fastapi_keycloak_middleware import get_user

from app.features.assomi.constants import AssomiApiErrorCode
from app.features.assomi.dependencies import AssomiQueryServiceDep
from app.features.assomi.list_dependencies import (
    get_assomi_task_filters,
    get_assomi_task_sort_params,
)
from app.features.assomi.messages import get_message
from app.features.assomi.query_params import AssomiTaskFilters
from app.features.assomi.schemas import AssomiTaskDetail, AssomiTaskListItem
from app.features.assomi.services.assomi_query_service import AssomiFileResolveResult
from app.features.auth.schemas import User
from app.features.nat.list_dependencies import get_pagination_params
from app.features.nat.pagination import PaginationParams
from app.features.nat.query_params import SortParams
from app.features.nat.schemas.pagination import PaginatedResponse

router = APIRouter(prefix='/assomi', tags=['assomi'])


def _file_response_from_resolve_result(
    result: AssomiFileResolveResult,
    *,
    assomi_task_id: UUID,
) -> FileResponse:
    if result.status == 'not_found':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'code': AssomiApiErrorCode.ASSOMI_TASK_NOT_FOUND,
                'message': get_message(AssomiApiErrorCode.ASSOMI_TASK_NOT_FOUND),
                'assomi_task_id': str(assomi_task_id),
            },
        )
    if result.status == 'not_ready':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                'code': AssomiApiErrorCode.ASSOMI_NOT_READY,
                'message': get_message(AssomiApiErrorCode.ASSOMI_NOT_READY),
                'assomi_task_id': str(assomi_task_id),
            },
        )
    if result.status == 'file_not_found':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'code': AssomiApiErrorCode.ASSOMI_FILE_NOT_FOUND,
                'message': get_message(AssomiApiErrorCode.ASSOMI_FILE_NOT_FOUND),
                'assomi_task_id': str(assomi_task_id),
            },
        )

    descriptor = result.descriptor
    if descriptor is None:
        raise RuntimeError(
            'ASSOMI file descriptor is required when resolve status is ok'
        )

    return FileResponse(
        path=descriptor.path,
        filename=descriptor.download_filename,
        media_type=descriptor.media_type,
    )


@router.get(
    '',
    response_model=PaginatedResponse[AssomiTaskListItem],
)
async def list_assomi_tasks(
    _user: Annotated[User, Depends(get_user)],
    query_service: AssomiQueryServiceDep,
    filters: Annotated[AssomiTaskFilters, Depends(get_assomi_task_filters)],
    sort: Annotated[SortParams, Depends(get_assomi_task_sort_params)],
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
) -> PaginatedResponse[AssomiTaskListItem]:
    return await query_service.list_assomi_tasks(
        filters=filters,
        sort=sort,
        pagination=pagination,
    )


@router.get(
    '/{assomi_task_id}',
    response_model=AssomiTaskDetail,
    responses={
        status.HTTP_404_NOT_FOUND: {
            'description': 'ASSOMI task not found',
        },
    },
)
async def get_assomi_task(
    assomi_task_id: UUID,
    _user: Annotated[User, Depends(get_user)],
    query_service: AssomiQueryServiceDep,
) -> AssomiTaskDetail:
    detail = await query_service.get_by_id(assomi_task_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'code': AssomiApiErrorCode.ASSOMI_TASK_NOT_FOUND,
                'message': get_message(AssomiApiErrorCode.ASSOMI_TASK_NOT_FOUND),
                'assomi_task_id': str(assomi_task_id),
            },
        )
    return detail


@router.get(
    '/{assomi_task_id}/file',
    response_class=FileResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            'description': 'ASSOMI task or file not found',
        },
        status.HTTP_409_CONFLICT: {
            'description': 'ASSOMI enrichment is not completed yet',
        },
    },
)
async def download_assomi_file(
    assomi_task_id: UUID,
    _user: Annotated[User, Depends(get_user)],
    query_service: AssomiQueryServiceDep,
) -> FileResponse:
    result = await query_service.resolve_file(assomi_task_id)
    return _file_response_from_resolve_result(
        result,
        assomi_task_id=assomi_task_id,
    )
