from types import TracebackType
from typing import Protocol, Self

from app.features.nat.repositories import (
    NatBatchRepository,
    NatDedupKeyRepository,
    NatIntakeRepository,
    NatIntakeRowErrorRepository,
    NatTaskRepository,
)


class UnitOfWorkProtocol(Protocol):
    @property
    def nat_intakes(self) -> NatIntakeRepository: ...

    @property
    def nat_intake_row_errors(self) -> NatIntakeRowErrorRepository: ...

    @property
    def nat_batches(self) -> NatBatchRepository: ...

    @property
    def nat_tasks(self) -> NatTaskRepository: ...

    @property
    def nat_dedup_keys(self) -> NatDedupKeyRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
