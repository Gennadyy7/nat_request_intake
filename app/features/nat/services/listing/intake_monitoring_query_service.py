from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.pagination import PaginationParams, build_paginated_response
from app.features.nat.query_params import NatIntakeFilters, SortParams
from app.features.nat.schemas.intake_monitoring import NatIntakeMonitoringListItem
from app.features.nat.schemas.pagination import PaginatedResponse
from app.features.nat.services.listing.intake_monitoring_mapping import (
    to_monitoring_list_item,
)


class IntakeMonitoringQueryService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def list_monitoring(
        self,
        *,
        filters: NatIntakeFilters,
        sort: SortParams,
        pagination: PaginationParams,
    ) -> PaginatedResponse[NatIntakeMonitoringListItem]:
        total_items = await self._uow.nat_intakes.count_filtered(filters)
        records = await self._uow.nat_intakes.list_monitoring_filtered(
            filters,
            sort,
            limit=pagination.limit,
            offset=pagination.offset,
        )
        items = [to_monitoring_list_item(record) for record in records]
        return build_paginated_response(
            items,
            total_items=total_items,
            page=pagination.page,
            limit=pagination.limit,
        )
