from typing import cast
from uuid import UUID

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.constants import InputColumnName, RowErrorCode
from app.features.nat.messages import get_message
from app.features.nat.models import NatIntakeRowError
from app.features.nat.pagination import PaginationParams, build_paginated_response
from app.features.nat.query_params import NatIntakeFilters, SortOrder, SortParams
from app.features.nat.schemas.intake_list import (
    NatIntakeDetail,
    NatIntakeListItem,
    NatIntakeRowErrorItem,
    NatIntakeRowErrorListResponse,
)
from app.features.nat.schemas.pagination import PaginatedResponse
from app.features.nat.services.listing.intake_mapping import (
    to_intake_detail,
    to_intake_list_item,
)


class IntakeQueryService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def list_intakes(
        self,
        *,
        filters: NatIntakeFilters,
        sort: SortParams,
        pagination: PaginationParams,
    ) -> PaginatedResponse[NatIntakeListItem]:
        total_items = await self._uow.nat_intakes.count_filtered(filters)
        records = await self._uow.nat_intakes.list_filtered(
            filters,
            sort,
            limit=pagination.limit,
            offset=pagination.offset,
        )
        items = [to_intake_list_item(record) for record in records]
        return build_paginated_response(
            items,
            total_items=total_items,
            page=pagination.page,
            limit=pagination.limit,
        )

    async def get_intake(self, intake_id: UUID) -> NatIntakeDetail | None:
        record = await self._uow.nat_intakes.get_list_record_by_id(intake_id)
        if record is None:
            return None
        return to_intake_detail(record)

    async def list_row_errors(
        self,
        intake_id: UUID,
        *,
        pagination: PaginationParams,
        sort_order: SortOrder,
    ) -> NatIntakeRowErrorListResponse | None:
        intake = await self._uow.nat_intakes.get_by_id(intake_id)
        if intake is None:
            return None
        total_items = await self._uow.nat_intake_row_errors.count_by_intake_id(
            intake_id
        )
        errors = await self._uow.nat_intake_row_errors.list_by_intake_id(
            intake_id,
            limit=pagination.limit,
            offset=pagination.offset,
            sort_order=sort_order,
        )
        items = [self._to_row_error_item(error) for error in errors]
        paginated = build_paginated_response(
            items,
            total_items=total_items,
            page=pagination.page,
            limit=pagination.limit,
        )
        return NatIntakeRowErrorListResponse(
            data=paginated.data,
            meta=paginated.meta,
        )

    def _to_row_error_item(self, error: NatIntakeRowError) -> NatIntakeRowErrorItem:
        column = InputColumnName(error.column) if error.column is not None else None
        error_code = _parse_row_error_code(error.error_code)
        return NatIntakeRowErrorItem(
            row_number=error.row_number,
            code=error_code,
            column=column,
            message=get_message(error_code),
        )


def _parse_row_error_code(value: str) -> RowErrorCode:
    return cast(RowErrorCode, value)
