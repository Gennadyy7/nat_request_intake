from app.features.nat.constants import NatRegionCode, ValidationErrorCode
from app.features.nat.services.optional_field import is_missing_optional_value


def validate_region(
    raw_value: str,
) -> tuple[NatRegionCode | None, ValidationErrorCode | None]:
    if is_missing_optional_value(raw_value):
        return None, None

    try:
        return NatRegionCode(raw_value.strip()), None
    except ValueError:
        return None, ValidationErrorCode.INVALID_REGION
