from app.features.nat.constants import AllowedFileExtension, ValidationErrorCode
from app.features.nat.services.parsing.file_parser import resolve_extension


def validate_filename(filename: str | None) -> ValidationErrorCode | None:
    if filename is None or not filename.strip():
        return ValidationErrorCode.MISSING_FILENAME
    return None


def validate_extension(
    filename: str,
) -> tuple[AllowedFileExtension | None, ValidationErrorCode | None]:
    extension = resolve_extension(filename)
    if extension is None:
        return None, ValidationErrorCode.INVALID_FILE_FORMAT
    return extension, None


def validate_non_empty_content(content: bytes) -> ValidationErrorCode | None:
    if not content:
        return ValidationErrorCode.EMPTY_FILE
    return None
