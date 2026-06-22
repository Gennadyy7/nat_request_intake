from typing import Annotated

from fastapi import Depends

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
from app.features.nat.services.listing.task_query_service import TaskQueryService
from app.features.nat.services.persistence.batch_persistence import (
    BatchPersistenceService,
)
from app.features.nat.services.persistence.file_storage import FileStorageService
from app.features.nat.services.processing.intake_processing_service import (
    IntakeProcessingService,
)
from app.features.nat.services.transformation.transformation_service import (
    TransformationService,
)


def get_file_storage_service() -> FileStorageService:
    return FileStorageService()


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


def get_intake_processing_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
) -> IntakeProcessingService:
    return IntakeProcessingService(uow=uow)
