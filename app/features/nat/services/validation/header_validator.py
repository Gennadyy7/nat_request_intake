from app.features.nat.constants import (
    REQUIRED_COLUMNS,
    InputColumnName,
    ValidationErrorCode,
)


def validate_headers(headers: list[str]) -> ValidationErrorCode | None:
    header_set = frozenset(headers)
    required_names = frozenset(column.value for column in REQUIRED_COLUMNS)
    if header_set != required_names:
        return ValidationErrorCode.INVALID_HEADERS
    return None


def get_row_value(row: dict[str, str], column: InputColumnName) -> str:
    return row.get(column.value, '')
