from dataclasses import dataclass

from app.core.config import Settings
from app.features.nat.constants import (
    COLUMN_TO_IP_FIELD,
    IP_COLUMNS,
    MANDATORY_VALUE_COLUMNS,
    REQUIRED_COLUMNS,
    InputColumnName,
    ValidationErrorCode,
)
from app.features.nat.schemas.validated_row import ValidatedRow
from app.features.nat.services.header_validator import get_row_value
from app.features.nat.services.optional_field import is_missing_optional_value
from app.features.nat.services.validators.date_validator import (
    DateValidationFailure,
    DateValidationSuccess,
    validate_date_field,
    validate_date_range,
)
from app.features.nat.services.validators.ip_validator import validate_ip_field
from app.features.nat.services.validators.region_validator import validate_region


@dataclass(frozen=True, slots=True)
class RowValidationError:
    row_number: int
    error_code: ValidationErrorCode
    column: InputColumnName | None = None


@dataclass(frozen=True, slots=True)
class RowValidationOutcome:
    validated_row: ValidatedRow | None
    errors: tuple[RowValidationError, ...]


def validate_row(
    row: dict[str, str],
    raw_field_count: int,
    row_index: int,
    settings: Settings,
) -> RowValidationOutcome:
    row_number = row_index + 1
    errors: list[RowValidationError] = []

    if raw_field_count != len(REQUIRED_COLUMNS) or not _has_expected_columns(row):
        errors.append(
            RowValidationError(
                row_number=row_number,
                error_code=ValidationErrorCode.ROW_COLUMN_COUNT_MISMATCH,
            )
        )
        return RowValidationOutcome(validated_row=None, errors=tuple(errors))

    for column in MANDATORY_VALUE_COLUMNS:
        raw_value = get_row_value(row, column)
        if not raw_value.strip():
            errors.append(
                RowValidationError(
                    row_number=row_number,
                    error_code=ValidationErrorCode.MISSING_REQUIRED_FIELD,
                    column=column,
                )
            )

    date_from: DateValidationSuccess | None = None
    date_to: DateValidationSuccess | None = None

    for column in (InputColumnName.DATE_FROM, InputColumnName.DATE_TO):
        raw_value = get_row_value(row, column)
        date_result = validate_date_field(raw_value, column, settings)
        if isinstance(date_result, DateValidationFailure):
            if not any(
                error.column == column
                and error.error_code == ValidationErrorCode.MISSING_REQUIRED_FIELD
                for error in errors
            ):
                errors.append(
                    RowValidationError(
                        row_number=row_number,
                        error_code=date_result.error_code,
                        column=date_result.column,
                    )
                )
            continue
        if column == InputColumnName.DATE_FROM:
            date_from = date_result
        else:
            date_to = date_result

    if date_from is not None and date_to is not None:
        range_error = validate_date_range(date_from.value, date_to.value)
        if range_error is not None:
            errors.append(
                RowValidationError(
                    row_number=row_number,
                    error_code=range_error.error_code,
                    column=range_error.column,
                )
            )

    for column in IP_COLUMNS:
        raw_value = get_row_value(row, column)
        ip_error = validate_ip_field(
            raw_value=raw_value,
            column=column,
            field_name=COLUMN_TO_IP_FIELD[column],
            settings=settings,
        )
        if ip_error is not None:
            errors.append(
                RowValidationError(
                    row_number=row_number,
                    error_code=ip_error.error_code,
                    column=ip_error.column,
                )
            )

    region_raw = get_row_value(row, InputColumnName.REGION)
    region_value, region_error_code = validate_region(region_raw, settings)
    if region_error_code is not None:
        errors.append(
            RowValidationError(
                row_number=row_number,
                error_code=region_error_code,
                column=InputColumnName.REGION,
            )
        )

    if errors:
        return RowValidationOutcome(validated_row=None, errors=tuple(errors))

    assert date_from is not None
    assert date_to is not None

    return RowValidationOutcome(
        validated_row=ValidatedRow(
            row_index=row_index,
            date_from=date_from.value,
            date_to=date_to.value,
            internal_ip=_optional_value(
                get_row_value(row, InputColumnName.INTERNAL_IP),
                settings,
            ),
            external_ip=_optional_value(
                get_row_value(row, InputColumnName.EXTERNAL_IP),
                settings,
            ),
            resource_ip=_optional_value(
                get_row_value(row, InputColumnName.RESOURCE_IP),
                settings,
            ),
            region=region_value,
        ),
        errors=(),
    )


def _has_expected_columns(row: dict[str, str]) -> bool:
    row_keys = frozenset(row.keys())
    required_names = frozenset(column.value for column in REQUIRED_COLUMNS)
    return row_keys == required_names and len(row) == len(REQUIRED_COLUMNS)


def _optional_value(raw_value: str, settings: Settings) -> str | None:
    if is_missing_optional_value(raw_value, settings):
        return None
    return raw_value.strip()
