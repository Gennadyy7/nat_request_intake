from typing import Annotated

from fastapi import Depends

from app.core.config import settings
from app.core.dependencies import get_uow
from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.assomi.services.assomi_query_service import AssomiQueryService
from app.features.assomi.services.manual_assomi_enrich_service import (
    ManualAssomiEnrichService,
)
from app.features.nat.services.persistence.file_storage import FileStorageService


def get_assomi_file_storage_service() -> FileStorageService:
    return FileStorageService(
        base_dir=settings.ASSOMI_BASE_DIR,
        use_date_subdirectory=False,
    )


def get_manual_assomi_input_file_storage_service() -> FileStorageService:
    return FileStorageService(
        base_dir=settings.SPIN_AGGREGATED_BASE_DIR,
        use_date_subdirectory=False,
    )


def get_assomi_query_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
    file_storage: Annotated[
        FileStorageService,
        Depends(get_assomi_file_storage_service),
    ],
) -> AssomiQueryService:
    return AssomiQueryService(uow=uow, file_storage=file_storage)


def get_manual_assomi_enrich_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
    file_storage: Annotated[
        FileStorageService,
        Depends(get_manual_assomi_input_file_storage_service),
    ],
) -> ManualAssomiEnrichService:
    return ManualAssomiEnrichService(uow=uow, file_storage=file_storage)


AssomiQueryServiceDep = Annotated[AssomiQueryService, Depends(get_assomi_query_service)]
ManualAssomiEnrichServiceDep = Annotated[
    ManualAssomiEnrichService,
    Depends(get_manual_assomi_enrich_service),
]
