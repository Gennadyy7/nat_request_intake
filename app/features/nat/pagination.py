from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil

from fastapi import HTTPException, status

from app.core.config import settings
from app.features.nat.query_params import SortOrder, SortParams
from app.features.nat.schemas.pagination import PaginatedResponse, PaginationMeta


@dataclass(frozen=True, slots=True)
class PaginationParams:
    page: int
    limit: int
    offset: int


def resolve_limit(requested_limit: int | None) -> int:
    if requested_limit is None:
        return settings.API_PAGINATION_DEFAULT_LIMIT
    return min(requested_limit, settings.API_PAGINATION_MAX_LIMIT)


def build_pagination_params(page: int, requested_limit: int | None) -> PaginationParams:
    limit = resolve_limit(requested_limit)
    offset = (page - 1) * limit
    return PaginationParams(page=page, limit=limit, offset=offset)


def build_pagination_meta(
    *,
    total_items: int,
    page: int,
    limit: int,
) -> PaginationMeta:
    if total_items == 0:
        total_pages = 0
        has_more = False
    else:
        total_pages = ceil(total_items / limit)
        has_more = page < total_pages
    return PaginationMeta(
        total_items=total_items,
        total_pages=total_pages,
        current_page=page,
        limit=limit,
        has_more=has_more,
    )


def build_paginated_response[ItemT](
    items: Sequence[ItemT],
    *,
    total_items: int,
    page: int,
    limit: int,
) -> PaginatedResponse[ItemT]:
    return PaginatedResponse(
        data=list(items),
        meta=build_pagination_meta(
            total_items=total_items,
            page=page,
            limit=limit,
        ),
    )


def resolve_sort_params(
    *,
    sort_by: str | None,
    sort_order: str | None,
    allowed_columns: frozenset[str],
    default_sort_by: str,
    default_sort_order: SortOrder = 'desc',
) -> SortParams:
    resolved_sort_by = sort_by if sort_by is not None else default_sort_by
    if resolved_sort_by not in allowed_columns:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                'error': 'invalid_sort_by',
                'sort_by': resolved_sort_by,
                'allowed': sorted(allowed_columns),
            },
        )

    if sort_order is None:
        resolved_sort_order = default_sort_order
    elif sort_order not in {'asc', 'desc'}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                'error': 'invalid_sort_order',
                'sort_order': sort_order,
                'allowed': ['asc', 'desc'],
            },
        )
    elif sort_order == 'asc':
        resolved_sort_order = 'asc'
    else:
        resolved_sort_order = 'desc'

    return SortParams(
        sort_by=resolved_sort_by,
        sort_order=resolved_sort_order,
    )
