from typing import NoReturn
from uuid import UUID

from fastapi import HTTPException, status

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.constants import ApiErrorCode
from app.features.nat.messages import get_message
from app.features.nat.schemas.intake_list import NatIntakeDetail
from app.features.nat.services.listing.intake_mapping import to_intake_detail


class IntakeProcessingService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def set_processing_paused(
        self,
        intake_id: UUID,
        *,
        paused: bool,
    ) -> NatIntakeDetail:
        intake = await self._uow.nat_intakes.get_by_id(intake_id)
        if intake is None:
            self._raise_intake_not_found(intake_id)

        batch = await self._uow.nat_batches.get_by_intake_id(intake_id)
        if batch is None:
            self._raise_intake_not_pausable(intake_id)

        if batch.result_emailed_at is not None:
            self._raise_batch_result_already_emailed(intake_id, batch.id)

        await self._uow.nat_batches.set_processing_paused(batch.id, paused=paused)
        await self._uow.commit()

        record = await self._uow.nat_intakes.get_list_record_by_id(intake_id)
        if record is None:
            self._raise_intake_not_found(intake_id)
        return to_intake_detail(record)

    def _raise_intake_not_found(self, intake_id: UUID) -> NoReturn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                'code': ApiErrorCode.INTAKE_NOT_FOUND,
                'message': get_message(ApiErrorCode.INTAKE_NOT_FOUND),
                'intake_id': str(intake_id),
            },
        )

    def _raise_intake_not_pausable(self, intake_id: UUID) -> NoReturn:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                'code': ApiErrorCode.INTAKE_NOT_PAUSABLE,
                'message': get_message(ApiErrorCode.INTAKE_NOT_PAUSABLE),
                'intake_id': str(intake_id),
            },
        )

    def _raise_batch_result_already_emailed(
        self,
        intake_id: UUID,
        batch_id: UUID,
    ) -> NoReturn:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                'code': ApiErrorCode.BATCH_RESULT_ALREADY_EMAILED,
                'message': get_message(ApiErrorCode.BATCH_RESULT_ALREADY_EMAILED),
                'intake_id': str(intake_id),
                'batch_id': str(batch_id),
            },
        )
