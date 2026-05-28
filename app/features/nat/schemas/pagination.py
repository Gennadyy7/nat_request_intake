from typing import Generic, TypeVar

from pydantic import BaseModel, Field

ItemT = TypeVar('ItemT')


class PaginationMeta(BaseModel):
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    current_page: int = Field(ge=1)
    limit: int = Field(ge=1)
    has_more: bool


class PaginatedResponse(BaseModel, Generic[ItemT]):
    data: list[ItemT]
    meta: PaginationMeta
