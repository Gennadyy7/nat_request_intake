from collections.abc import Sequence
from uuid import UUID, uuid4

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.constants import NatTaskStatus
from app.features.nat.domain.transformed_row import TransformedRow
from app.features.nat.models import NatBatch, NatTask


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

        tasks = [
            NatTask(
                id=uuid4(),
                batch_id=batch_id,
                nat_request_id=None,
                datetime_from=row.datetime_from,
                datetime_to=row.datetime_to,
                src_xlated=row.src_xlated,
                src_port_xlated=row.src_port_xlated,
                src=row.src,
                src_port=row.src_port,
                dst=row.dst,
                dst_port=row.dst_port,
                region=row.region,
                status=NatTaskStatus.QUEUED,
            )
            for row in transformed_rows
        ]
        await self._uow.nat_tasks.create_many(tasks)

        return batch
