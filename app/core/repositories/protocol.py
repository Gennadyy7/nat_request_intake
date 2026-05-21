from collections.abc import Sequence
from typing import Protocol, TypeVar

T = TypeVar('T')
ID_contra = TypeVar('ID_contra', contravariant=True)


class RepositoryProtocol(Protocol[T, ID_contra]):
    async def get_by_id(self, entity_id: ID_contra) -> T | None: ...

    async def get_all(self, limit: int, offset: int) -> Sequence[T]: ...

    async def create(self, entity: T) -> T: ...

    async def update(self, entity: T) -> T: ...

    async def delete(self, entity: T) -> bool: ...
