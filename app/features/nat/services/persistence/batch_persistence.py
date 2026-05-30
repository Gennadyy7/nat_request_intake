from collections.abc import Sequence
from uuid import UUID

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.domain.transformed_row import TransformedRow
from app.features.nat.models import NatBatch


class BatchPersistenceService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def persist(
        self,
        *,
        intake_id: UUID,
        batch_id: UUID,
        storage_path: str,
        row_count: int,
        transformed_rows: Sequence[TransformedRow],
    ) -> NatBatch:
        batch = NatBatch(
            id=batch_id,
            intake_id=intake_id,
            file_name=storage_path,
            row_count=row_count,
        )
        await self._uow.nat_batches.create(batch)
        await self._uow.nat_tasks.create_many_from_rows(transformed_rows, batch_id)
        return batch
