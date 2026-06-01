from dataclasses import dataclass
from datetime import datetime

from dateutil import parser as dateutil_parser

from app.core.config import settings
from app.features.nat.constants import InputColumnName, ValidationErrorCode


@dataclass(frozen=True, slots=True)
class DateValidationSuccess:
    value: datetime


@dataclass(frozen=True, slots=True)
class DateValidationFailure:
    error_code: ValidationErrorCode
    column: InputColumnName


DateValidationResult = DateValidationSuccess | DateValidationFailure


def validate_required_date(
    raw_value: str,
    column: InputColumnName,
) -> DateValidationFailure | None:
    if not raw_value.strip():
        return DateValidationFailure(
            error_code=ValidationErrorCode.MISSING_REQUIRED_FIELD,
            column=column,
        )
    return None


def parse_date(raw_value: str) -> datetime | None:
    stripped = raw_value.strip()
    for date_format in settings.NAT_DATE_INPUT_FORMATS:
        try:
            return datetime.strptime(stripped, date_format)
        except ValueError:
            continue
    try:
        parsed_value = dateutil_parser.parse(stripped)
    except (ValueError, TypeError, OverflowError):
        return None
    if isinstance(parsed_value, datetime):
        return parsed_value
    return None


def validate_date_field(
    raw_value: str,
    column: InputColumnName,
) -> DateValidationResult:
    missing_error = validate_required_date(raw_value, column)
    if missing_error is not None:
        return missing_error

    parsed = parse_date(raw_value)
    if parsed is None:
        return DateValidationFailure(
            error_code=ValidationErrorCode.INVALID_DATE_FORMAT,
            column=column,
        )
    return DateValidationSuccess(value=parsed)


def validate_date_range(
    date_from: datetime,
    date_to: datetime,
) -> DateValidationFailure | None:
    if date_to < date_from:
        return DateValidationFailure(
            error_code=ValidationErrorCode.INVALID_DATE_RANGE,
            column=InputColumnName.DATE_TO,
        )
    return None
