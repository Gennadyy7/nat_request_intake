from collections.abc import Sequence
from dataclasses import dataclass

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.constants import DeduplicationErrorCode
from app.features.nat.domain.validated_row import ValidatedRow
from app.features.nat.services.deduplication.deduplication_key import (
    build_deduplication_key,
    build_key_hash,
)


@dataclass(frozen=True, slots=True)
class DeduplicationRowError:
    row_number: int
    error_code: DeduplicationErrorCode


@dataclass(frozen=True, slots=True)
class DeduplicationOutcome:
    accepted_rows: tuple[ValidatedRow, ...]
    errors: tuple[DeduplicationRowError, ...]


@dataclass(frozen=True, slots=True)
class DeduplicationRegistrationOutcome:
    registered_rows: tuple[ValidatedRow, ...]
    errors: tuple[DeduplicationRowError, ...]


class DeduplicationService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def check_duplicates(
        self,
        rows: Sequence[ValidatedRow],
    ) -> DeduplicationOutcome:
        accepted_rows: list[ValidatedRow] = []
        errors: list[DeduplicationRowError] = []
        seen_hashes: set[str] = set()

        for row in rows:
            deduplication_key = build_deduplication_key(row)
            key_hash = build_key_hash(deduplication_key)

            if key_hash in seen_hashes:
                errors.append(
                    DeduplicationRowError(
                        row_number=row.row_number,
                        error_code=DeduplicationErrorCode.DUPLICATE_REQUEST,
                    )
                )
                continue
            seen_hashes.add(key_hash)

            if await self._uow.nat_dedup_keys.exists_within_window(deduplication_key):
                errors.append(
                    DeduplicationRowError(
                        row_number=row.row_number,
                        error_code=DeduplicationErrorCode.DUPLICATE_REQUEST,
                    )
                )
                continue

            accepted_rows.append(row)

        return DeduplicationOutcome(
            accepted_rows=tuple(accepted_rows),
            errors=tuple(errors),
        )

    async def register_accepted_rows(
        self,
        rows: Sequence[ValidatedRow],
    ) -> DeduplicationRegistrationOutcome:
        if not rows:
            return DeduplicationRegistrationOutcome(
                registered_rows=(),
                errors=(),
            )

        await self._uow.nat_dedup_keys.purge_expired()

        registered_rows: list[ValidatedRow] = []
        errors: list[DeduplicationRowError] = []

        for row in rows:
            deduplication_key = build_deduplication_key(row)
            registered = await self._uow.nat_dedup_keys.register_if_absent(
                deduplication_key
            )
            if registered:
                registered_rows.append(row)
            else:
                errors.append(
                    DeduplicationRowError(
                        row_number=row.row_number,
                        error_code=DeduplicationErrorCode.DUPLICATE_REQUEST,
                    )
                )

        return DeduplicationRegistrationOutcome(
            registered_rows=tuple(registered_rows),
            errors=tuple(errors),
        )
