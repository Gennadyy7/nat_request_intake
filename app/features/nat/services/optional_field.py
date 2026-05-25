from app.core.config import settings


def is_missing_optional_value(raw_value: str) -> bool:
    stripped = raw_value.strip()
    return not stripped or stripped == settings.NAT_MISSING_FIELD_PLACEHOLDER
