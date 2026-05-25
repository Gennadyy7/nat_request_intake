from collections.abc import Sequence
from dataclasses import dataclass

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.constants import DeduplicationErrorCode
from app.features.nat.schemas.validated_row import ValidatedRow
from app.features.nat.services.deduplication.deduplication_key import (
    build_deduplication_key,
)


@dataclass(frozen=True, slots=True)
class DeduplicationRowError:
    row_number: int
    error_code: DeduplicationErrorCode


@dataclass(frozen=True, slots=True)
class DeduplicationOutcome:
    accepted_rows: tuple[ValidatedRow, ...]
    errors: tuple[DeduplicationRowError, ...]


class DeduplicationService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def deduplicate(
        self,
        rows: Sequence[ValidatedRow],
    ) -> DeduplicationOutcome:
        accepted_rows: list[ValidatedRow] = []
        errors: list[DeduplicationRowError] = []

        for row in rows:
            deduplication_key = build_deduplication_key(row)
            registered = await self._uow.nat_dedup_keys.register_if_absent(
                deduplication_key
            )
            if registered:
                accepted_rows.append(row)
                continue

            errors.append(
                DeduplicationRowError(
                    row_number=row.row_number,
                    error_code=DeduplicationErrorCode.DUPLICATE_REQUEST,
                )
            )

        return DeduplicationOutcome(
            accepted_rows=tuple(accepted_rows),
            errors=tuple(errors),
        )
