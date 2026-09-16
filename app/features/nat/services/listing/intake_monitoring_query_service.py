from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.pagination import PaginationParams, build_pagination_meta
from app.features.nat.query_params import NatIntakeMonitoringFilters, SortParams
from app.features.nat.schemas.intake_monitoring import NatIntakeMonitoringListResponse
from app.features.nat.services.listing.intake_monitoring_mapping import (
    to_monitoring_list_item,
)


class IntakeMonitoringQueryService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def list_monitoring(
        self,
        *,
        filters: NatIntakeMonitoringFilters,
        sort: SortParams,
        pagination: PaginationParams,
    ) -> NatIntakeMonitoringListResponse:
        total_items = await self._uow.nat_intakes.count_monitoring_filtered(filters)
        records = await self._uow.nat_intakes.list_monitoring_filtered(
            filters,
            sort,
            limit=pagination.limit,
            offset=pagination.offset,
        )
        items = [to_monitoring_list_item(record) for record in records]
        global_processing_paused = (
            await self._uow.nat_global_processing.is_processing_paused()
        )
        return NatIntakeMonitoringListResponse(
            data=items,
            meta=build_pagination_meta(
                total_items=total_items,
                page=pagination.page,
                limit=pagination.limit,
            ),
            global_processing_paused=global_processing_paused,
        )
