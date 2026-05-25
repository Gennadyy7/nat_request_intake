from typing import Annotated

from fastapi import Depends

from app.core.dependencies import get_uow
from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.services.deduplication.deduplication_service import (
    DeduplicationService,
)
from app.features.nat.services.intake_service import IntakeService


def get_deduplication_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
) -> DeduplicationService:
    return DeduplicationService(uow=uow)


def get_intake_service(
    deduplication_service: Annotated[
        DeduplicationService,
        Depends(get_deduplication_service),
    ],
) -> IntakeService:
    return IntakeService(deduplication_service=deduplication_service)
