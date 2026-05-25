from app.features.nat.constants import NatRegionCode, ValidationErrorCode


def validate_region(
    raw_value: str,
) -> tuple[NatRegionCode | None, ValidationErrorCode | None]:
    stripped = raw_value.strip()
    if not stripped:
        return None, None

    try:
        return NatRegionCode(stripped), None
    except ValueError:
        return None, ValidationErrorCode.INVALID_REGION
