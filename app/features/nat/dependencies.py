from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from app.core.client_credentials import ClientCredentialsTokenProvider
from app.core.config import settings
from app.core.dependencies import get_uow
from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.services.deduplication.deduplication_service import (
    DeduplicationService,
)
from app.features.nat.services.intake.intake_service import IntakeService
from app.features.nat.services.listing.batch_query_service import BatchQueryService
from app.features.nat.services.listing.intake_monitoring_query_service import (
    IntakeMonitoringQueryService,
)
from app.features.nat.services.listing.intake_query_service import IntakeQueryService
from app.features.nat.services.listing.result_processing_query_service import (
    ResultProcessingQueryService,
)
from app.features.nat.services.listing.task_query_service import TaskQueryService
from app.features.nat.services.manual_spin_match_client import MatchSpinClient
from app.features.nat.services.manual_spin_match_service import ManualSpinMatchService
from app.features.nat.services.persistence.batch_persistence import (
    BatchPersistenceService,
)
from app.features.nat.services.persistence.file_storage import FileStorageService
from app.features.nat.services.processing.global_processing_service import (
    GlobalProcessingService,
)
from app.features.nat.services.processing.intake_processing_service import (
    IntakeProcessingService,
)
from app.features.nat.services.transformation.transformation_service import (
    TransformationService,
)


def get_file_storage_service() -> FileStorageService:
    return FileStorageService()


def get_manual_spin_file_storage_service() -> FileStorageService:
    return FileStorageService(
        base_dir=settings.SPIN_AGGREGATED_BASE_DIR,
        use_date_subdirectory=False,
    )


async def get_match_spin_client() -> AsyncIterator[MatchSpinClient]:
    keycloak_base_url = settings.KEYCLOAK_URL.rstrip('/')
    token_provider = ClientCredentialsTokenProvider(
        token_url=(
            f'{keycloak_base_url}/realms/{settings.KEYCLOAK_REALM}'
            '/protocol/openid-connect/token'
        ),
        client_id=settings.NAT_BATCH_NOTIFY_WORKER_KEYCLOAK_CLIENT_ID,
        client_secret=settings.NAT_BATCH_NOTIFY_WORKER_KEYCLOAK_CLIENT_SECRET,
    )
    async with MatchSpinClient(token_provider) as client:
        yield client


def get_manual_spin_match_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
    file_storage: Annotated[
        FileStorageService,
        Depends(get_manual_spin_file_storage_service),
    ],
    match_spin_client: Annotated[MatchSpinClient, Depends(get_match_spin_client)],
) -> ManualSpinMatchService:
    return ManualSpinMatchService(
        uow=uow,
        file_storage=file_storage,
        match_spin_client=match_spin_client,
    )


def get_transformation_service() -> TransformationService:
    return TransformationService()


def get_deduplication_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
) -> DeduplicationService:
    return DeduplicationService(uow=uow)


def get_batch_persistence_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
) -> BatchPersistenceService:
    return BatchPersistenceService(uow=uow)


def get_intake_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
    deduplication_service: Annotated[
        DeduplicationService,
        Depends(get_deduplication_service),
    ],
    transformation_service: Annotated[
        TransformationService,
        Depends(get_transformation_service),
    ],
    file_storage_service: Annotated[
        FileStorageService,
        Depends(get_file_storage_service),
    ],
    batch_persistence_service: Annotated[
        BatchPersistenceService,
        Depends(get_batch_persistence_service),
    ],
) -> IntakeService:
    return IntakeService(
        uow=uow,
        deduplication_service=deduplication_service,
        transformation_service=transformation_service,
        file_storage_service=file_storage_service,
        batch_persistence_service=batch_persistence_service,
    )


def get_intake_query_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
) -> IntakeQueryService:
    return IntakeQueryService(uow=uow)


def get_intake_monitoring_query_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
) -> IntakeMonitoringQueryService:
    return IntakeMonitoringQueryService(uow=uow)


def get_batch_query_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
    file_storage_service: Annotated[
        FileStorageService,
        Depends(get_file_storage_service),
    ],
) -> BatchQueryService:
    return BatchQueryService(uow=uow, file_storage=file_storage_service)


def get_task_query_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
) -> TaskQueryService:
    return TaskQueryService(uow=uow)


def get_result_processing_query_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
    file_storage: Annotated[
        FileStorageService,
        Depends(get_manual_spin_file_storage_service),
    ],
) -> ResultProcessingQueryService:
    return ResultProcessingQueryService(uow=uow, file_storage=file_storage)


def get_intake_processing_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
) -> IntakeProcessingService:
    return IntakeProcessingService(uow=uow)


def get_global_processing_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
) -> GlobalProcessingService:
    return GlobalProcessingService(uow=uow)
