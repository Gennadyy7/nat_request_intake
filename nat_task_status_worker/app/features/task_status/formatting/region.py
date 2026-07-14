_ALL_REGIONS = '1,2,3,4,5,6,7,8'


def format_region_for_nat_value(region: str, *, missing_placeholder: str) -> str:
    if region == missing_placeholder:
        return _ALL_REGIONS
    return region
