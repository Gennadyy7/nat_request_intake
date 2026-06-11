from __future__ import annotations

from nat_task_status_worker.app.core.config import settings

_ALL_REGIONS = '1,2,3,4,5,6,7,8'


def format_region_for_nat_value(region: str, *, missing_placeholder: str) -> str:
    if region == missing_placeholder:
        return _ALL_REGIONS
    return region


def format_region_for_nat(region: str) -> str:
    return format_region_for_nat_value(
        region,
        missing_placeholder=settings.NAT_MISSING_FIELD_PLACEHOLDER,
    )
