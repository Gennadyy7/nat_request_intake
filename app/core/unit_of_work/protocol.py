from types import TracebackType
from typing import Protocol, Self


class UnitOfWorkProtocol(Protocol):
    # @property
    # def items(self) -> ItemRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
