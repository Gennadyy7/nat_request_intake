from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi_keycloak_middleware import get_user
from pydantic import EmailStr

from app.core.config import settings
from app.features.auth.dependencies import (
    get_b2b_sender_email,
    get_sender_email,
    require_email_poller_service,
)
from app.features.auth.schemas import User
from app.features.nat.constants import ApiErrorCode, ResultProcessingGetStatus
from app.features.nat.dependencies import (
    get_batch_query_service,
    get_intake_monitoring_query_service,
    get_intake_processing_service,
    get_intake_query_service,
    get_intake_service,
    get_result_processing_query_service,
    get_task_query_service,
)
from app.features.nat.list_dependencies import (
    get_nat_batch_filters,
    get_nat_batch_sort_params,
    get_nat_intake_filters,
    get_nat_intake_monitoring_filters,
    get_nat_intake_row_errors_sort_order,
    get_nat_intake_sort_params,
    get_nat_task_filters,
    get_nat_task_sort_params,
    get_pagination_params,
)
from app.features.nat.messages import get_message
from app.features.nat.pagination import PaginationParams
from app.features.nat.query_params import (
    NatBatchFilters,
    NatIntakeFilters,
    NatIntakeMonitoringFilters,
    NatTaskFilters,
    SortOrder,
    SortParams,
)
from app.features.nat.schemas.batch_list import NatBatchDetail, NatBatchListItem
from app.features.nat.schemas.intake import IntakeResponse
from app.features.nat.schemas.intake_list import (
    NatIntakeDetail,
    NatIntakeListItem,
    NatIntakeRowErrorListResponse,
)
from app.features.nat.schemas.intake_monitoring import NatIntakeMonitoringListItem
from app.features.nat.schemas.intake_processing import IntakeProcessingUpdate
from app.features.nat.schemas.pagination import PaginatedResponse
from app.features.nat.schemas.result_processing import NatResultProcessingDetail
from app.features.nat.schemas.task_list import NatTaskDetail, NatTaskListItem
from app.features.nat.services.intake.intake_service import IntakeService
from app.features.nat.services.intake.intake_upload import process_intake_upload
from app.features.nat.services.listing.batch_query_service import BatchQueryService
from app.features.nat.services.listing.intake_monitoring_query_service import (
    IntakeMonitoringQueryService,
)
from app.features.nat.services.listing.intake_query_service import IntakeQueryService
from app.features.nat.services.listing.result_processing_query_service import (
    ResultProcessingQueryService,
)
from app.features.nat.services.listing.task_query_service import TaskQueryService
from app.features.nat.services.processing.intake_processing_service import (
    IntakeProcessingService,
)

router = APIRouter(prefix='/nat', tags=['nat'])


@router.post(
    '/intake',
    response_model=IntakeResponse,
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            'description': (
                'Intake rejected, authenticated user has no email claim, or auth error'
            ),
            'model': IntakeResponse,
        },
    },
)
async def intake_file(
    sender_email: Annotated[EmailStr, Depends(get_sender_email)],
    service: Annotated[IntakeService, Depends(get_intake_service)],
    file: Annotated[UploadFile, File()],
) -> IntakeResponse | JSONResponse:
    content = await file.read()
    return await process_intake_upload(
        service=service,
        filename=file.filename,
        content=content,
        sender_email=sender_email,
        enforce_max_date_range=settings.NAT_WEB_INTAKE_ENFORCE_MAX_DATE_RANGE,
    )


@router.post(
    '/intake/internal',
    response_model=IntakeResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            'description': 'Missing or invalid service account token',
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            'description': 'Intake rejected or invalid sender_email form field',
            'model': IntakeResponse,
        },
    },
)
async def intake_file_internal(
    _service_account: Annotated[User, Depends(require_email_poller_service)],
    sender_email: Annotated[EmailStr, Depends(get_b2b_sender_email)],
    service: Annotated[IntakeService, Depends(get_intake_service)],
    file: Annotated[UploadFile, File()],
) -> IntakeResponse | JSONResponse:
    content = await file.read()
    return await process_intake_upload(
        service=service,
        filename=file.filename,
        content=content,
        sender_email=sender_email,
        enforce_max_date_range=True,
    )


@router.get('/intakes', response_model=PaginatedResponse[NatIntakeListItem])
async def list_intakes(
    _user: Annotated[User, Depends(get_user)],
    query_service: Annotated[IntakeQueryService, Depends(get_intake_query_service)],
    filters: Annotated[NatIntakeFilters, Depends(get_nat_intake_filters)],
    sort: Annotated[SortParams, Depends(get_nat_intake_sort_params)],
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
) -> PaginatedResponse[NatIntakeListItem]:
    return await query_service.list_intakes(
        filters=filters,
        sort=sort,
        pagination=pagination,
    )


@router.get(
    '/intakes/monitoring',
    response_model=PaginatedResponse[NatIntakeMonitoringListItem],
)
async def list_intakes_monitoring(
    _user: Annotated[User, Depends(get_user)],
    query_service: Annotated[
        IntakeMonitoringQueryService,
        Depends(get_intake_monitoring_query_service),
    ],
    filters: Annotated[
        NatIntakeMonitoringFilters,
        Depends(get_nat_intake_monitoring_filters),
    ],
    sort: Annotated[SortParams, Depends(get_nat_intake_sort_params)],
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
) -> PaginatedResponse[NatIntakeMonitoringListItem]:
    return await query_service.list_monitoring(
        filters=filters,
        sort=sort,
        pagination=pagination,
    )


@router.get('/intakes/{intake_id}', response_model=NatIntakeDetail)
async def get_intake(
    intake_id: UUID,
    _user: Annotated[User, Depends(get_user)],
    query_service: Annotated[IntakeQueryService, Depends(get_intake_query_service)],
) -> NatIntakeDetail:
    detail = await query_service.get_intake(intake_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'code': ApiErrorCode.INTAKE_NOT_FOUND,
                'message': get_message(ApiErrorCode.INTAKE_NOT_FOUND),
                'intake_id': str(intake_id),
            },
        )
    return detail


@router.patch(
    '/intakes/{intake_id}/processing',
    response_model=NatIntakeDetail,
    responses={
        status.HTTP_404_NOT_FOUND: {
            'description': 'Intake not found',
        },
        status.HTTP_409_CONFLICT: {
            'description': 'Intake cannot be paused or batch already notified',
        },
    },
)
async def update_intake_processing(
    intake_id: UUID,
    payload: IntakeProcessingUpdate,
    _user: Annotated[User, Depends(get_user)],
    processing_service: Annotated[
        IntakeProcessingService,
        Depends(get_intake_processing_service),
    ],
) -> NatIntakeDetail:
    return await processing_service.set_processing_paused(
        intake_id,
        paused=payload.paused,
    )


@router.get(
    '/intakes/{intake_id}/row-errors',
    response_model=NatIntakeRowErrorListResponse,
)
async def list_intake_row_errors(
    intake_id: UUID,
    _user: Annotated[User, Depends(get_user)],
    query_service: Annotated[IntakeQueryService, Depends(get_intake_query_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
    sort_order: Annotated[
        SortOrder,
        Depends(get_nat_intake_row_errors_sort_order),
    ],
) -> NatIntakeRowErrorListResponse:
    result = await query_service.list_row_errors(
        intake_id,
        pagination=pagination,
        sort_order=sort_order,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'code': ApiErrorCode.INTAKE_NOT_FOUND,
                'message': get_message(ApiErrorCode.INTAKE_NOT_FOUND),
                'intake_id': str(intake_id),
            },
        )
    return result


@router.get('/batches', response_model=PaginatedResponse[NatBatchListItem])
async def list_batches(
    _user: Annotated[User, Depends(get_user)],
    query_service: Annotated[BatchQueryService, Depends(get_batch_query_service)],
    filters: Annotated[NatBatchFilters, Depends(get_nat_batch_filters)],
    sort: Annotated[SortParams, Depends(get_nat_batch_sort_params)],
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
) -> PaginatedResponse[NatBatchListItem]:
    return await query_service.list_batches(
        filters=filters,
        sort=sort,
        pagination=pagination,
    )


@router.get('/batches/{batch_id}', response_model=NatBatchDetail)
async def get_batch(
    batch_id: UUID,
    _user: Annotated[User, Depends(get_user)],
    query_service: Annotated[BatchQueryService, Depends(get_batch_query_service)],
) -> NatBatchDetail:
    detail = await query_service.get_batch(batch_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'code': ApiErrorCode.BATCH_NOT_FOUND,
                'message': get_message(ApiErrorCode.BATCH_NOT_FOUND),
                'batch_id': str(batch_id),
            },
        )
    return detail


@router.get(
    '/batches/{batch_id}/result-processing',
    response_model=NatResultProcessingDetail,
    responses={
        status.HTTP_404_NOT_FOUND: {
            'description': 'Batch or result processing task not found',
        },
    },
)
async def get_batch_result_processing(
    batch_id: UUID,
    _user: Annotated[User, Depends(get_user)],
    query_service: Annotated[
        ResultProcessingQueryService,
        Depends(get_result_processing_query_service),
    ],
) -> NatResultProcessingDetail:
    result = await query_service.get_by_batch_id(batch_id)
    if result.status == ResultProcessingGetStatus.BATCH_NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'code': ApiErrorCode.BATCH_NOT_FOUND,
                'message': get_message(ApiErrorCode.BATCH_NOT_FOUND),
                'batch_id': str(batch_id),
            },
        )
    if result.status == ResultProcessingGetStatus.RESULT_PROCESSING_NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'code': ApiErrorCode.RESULT_PROCESSING_NOT_FOUND,
                'message': get_message(ApiErrorCode.RESULT_PROCESSING_NOT_FOUND),
                'batch_id': str(batch_id),
            },
        )
    assert result.detail is not None
    return result.detail


@router.get(
    '/batches/{batch_id}/file',
    response_class=FileResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            'description': 'Batch or source file not found',
        },
    },
)
async def download_batch_file(
    batch_id: UUID,
    _user: Annotated[User, Depends(get_user)],
    query_service: Annotated[BatchQueryService, Depends(get_batch_query_service)],
) -> FileResponse:
    result = await query_service.resolve_source_file(batch_id)
    if result.status == 'batch_not_found':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'code': ApiErrorCode.BATCH_NOT_FOUND,
                'message': get_message(ApiErrorCode.BATCH_NOT_FOUND),
                'batch_id': str(batch_id),
            },
        )
    if result.status == 'file_not_found':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'code': ApiErrorCode.BATCH_FILE_NOT_FOUND,
                'message': get_message(ApiErrorCode.BATCH_FILE_NOT_FOUND),
                'batch_id': str(batch_id),
            },
        )
    descriptor = result.descriptor
    # status 'ok' always sets descriptor; this guards the impossible case for type checkers.
    if descriptor is None:
        raise RuntimeError(
            'Batch file descriptor is required when resolve status is ok'
        )
    return FileResponse(
        path=descriptor.path,
        filename=descriptor.download_filename,
        media_type=descriptor.media_type,
    )


@router.get('/tasks', response_model=PaginatedResponse[NatTaskListItem])
async def list_tasks(
    _user: Annotated[User, Depends(get_user)],
    query_service: Annotated[TaskQueryService, Depends(get_task_query_service)],
    filters: Annotated[NatTaskFilters, Depends(get_nat_task_filters)],
    sort: Annotated[SortParams, Depends(get_nat_task_sort_params)],
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
) -> PaginatedResponse[NatTaskListItem]:
    return await query_service.list_tasks(
        filters=filters,
        sort=sort,
        pagination=pagination,
    )


@router.get('/tasks/{task_id}', response_model=NatTaskDetail)
async def get_task(
    task_id: UUID,
    _user: Annotated[User, Depends(get_user)],
    query_service: Annotated[TaskQueryService, Depends(get_task_query_service)],
) -> NatTaskDetail:
    detail = await query_service.get_task(task_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'code': ApiErrorCode.TASK_NOT_FOUND,
                'message': get_message(ApiErrorCode.TASK_NOT_FOUND),
                'task_id': str(task_id),
            },
        )
    return detail
