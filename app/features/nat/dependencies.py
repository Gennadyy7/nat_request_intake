from typing import Annotated

from fastapi import Depends

from app.core.dependencies import get_uow
from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.services.intake_service import IntakeService


def get_intake_service(
    uow: Annotated[UnitOfWorkProtocol, Depends(get_uow)],
) -> IntakeService:
    return IntakeService(uow=uow)
