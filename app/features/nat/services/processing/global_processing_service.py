from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.schemas.intake_processing import GlobalProcessingState


class GlobalProcessingService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def get_processing_paused(self) -> GlobalProcessingState:
        paused = await self._uow.nat_global_processing.is_processing_paused()
        return GlobalProcessingState(paused=paused)

    async def set_processing_paused(self, *, paused: bool) -> GlobalProcessingState:
        await self._uow.nat_global_processing.set_processing_paused(paused=paused)
        await self._uow.commit()
        return GlobalProcessingState(paused=paused)
