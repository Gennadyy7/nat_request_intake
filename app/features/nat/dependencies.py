from typing import Annotated

from fastapi import Depends

from app.core.dependencies import get_uow
from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.services.deduplication.deduplication_service import (
    DeduplicationService,
)
from app.features.nat.services.intake.intake_service import IntakeService
from app.features.nat.services.persistence.batch_persistence import (
    BatchPersistenceService,
)
from app.features.nat.services.persistence.file_storage import FileStorageService
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
