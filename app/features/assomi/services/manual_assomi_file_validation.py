import csv
from io import StringIO

from app.features.assomi.constants import ASSOMI_CSV_DELIMITER, ASSOMI_CSV_HEADERS
from app.features.nat.constants import AllowedFileExtension, ValidationErrorCode
from app.features.nat.services.intake.file_gate import (
    validate_filename,
    validate_non_empty_content,
)
from app.features.nat.services.parsing.file_parser import resolve_extension


def validate_manual_assomi_upload(
    *,
    filename: str | None,
    content: bytes,
) -> ValidationErrorCode | None:
    filename_error = validate_filename(filename)
    if filename_error is not None:
        return filename_error
    assert filename is not None
    if resolve_extension(filename) != AllowedFileExtension.CSV:
        return ValidationErrorCode.MANUAL_ASSOMI_CSV_REQUIRED
    empty_error = validate_non_empty_content(content)
    if empty_error is not None:
        return empty_error
    try:
        text = _decode_csv_text(content)
    except ValueError:
        return ValidationErrorCode.INVALID_FILE_FORMAT
    return _validate_spin_matched_csv_text(text)


def _decode_csv_text(content: bytes) -> str:
    for encoding in ('utf-8-sig', 'cp1251'):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError('Unable to decode content as utf-8-sig or cp1251')


def _validate_spin_matched_csv_text(text: str) -> ValidationErrorCode | None:
    reader = csv.reader(StringIO(text), delimiter=ASSOMI_CSV_DELIMITER)
    login_count = 0
    for row in reader:
        if not row:
            continue
        cells = [cell.strip() for cell in row]
        if not any(cells):
            continue
        if _is_assomi_result_header(cells):
            return ValidationErrorCode.MANUAL_ASSOMI_WRONG_FILE_KIND
        if cells[0]:
            login_count += 1
    if login_count == 0:
        return ValidationErrorCode.MANUAL_ASSOMI_NO_LOGINS
    return None


def _is_assomi_result_header(cells: list[str]) -> bool:
    if len(cells) < len(ASSOMI_CSV_HEADERS):
        return False
    return tuple(cells[: len(ASSOMI_CSV_HEADERS)]) == ASSOMI_CSV_HEADERS
