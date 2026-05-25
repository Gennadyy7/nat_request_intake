from pydantic import EmailStr

from app.core.config import settings
from app.core.logging import get_logger
from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.constants import IntakeStatus, ValidationErrorCode
from app.features.nat.schemas.intake import (
    FileErrorResponse,
    IntakeResponse,
    RowErrorResponse,
    ValidatedRowResponse,
)
from app.features.nat.schemas.validated_row import ValidatedRow
from app.features.nat.services.deduplication.deduplication_service import (
    deduplicate_rows,
)
from app.features.nat.services.file_gate import (
    validate_extension,
    validate_filename,
    validate_non_empty_content,
)
from app.features.nat.services.file_parser import parse_file_content
from app.features.nat.services.header_validator import validate_headers
from app.features.nat.services.row_validator import validate_row

logger = get_logger(__name__)


class IntakeService:
    async def process(
        self,
        *,
        filename: str | None,
        content: bytes,
        sender_email: EmailStr,
        uow: UnitOfWorkProtocol,
    ) -> IntakeResponse:
        resolved_filename = filename or ''

        filename_error = validate_filename(filename)
        if filename_error is not None:
            return self._build_file_rejection(
                file_name=resolved_filename,
                sender_email=sender_email,
                error_code=filename_error,
            )

        assert filename is not None

        extension, extension_error = validate_extension(filename)
        if extension_error is not None:
            return self._build_file_rejection(
                file_name=filename,
                sender_email=sender_email,
                error_code=extension_error,
            )

        assert extension is not None

        empty_error = validate_non_empty_content(content)
        if empty_error is not None:
            return self._build_file_rejection(
                file_name=filename,
                sender_email=sender_email,
                error_code=empty_error,
            )

        parsed = parse_file_content(content, extension)

        if not parsed.headers and not parsed.rows:
            return self._build_file_rejection(
                file_name=filename,
                sender_email=sender_email,
                error_code=ValidationErrorCode.EMPTY_FILE,
            )

        header_error = validate_headers(parsed.headers)
        if header_error is not None:
            return self._build_file_rejection(
                file_name=filename,
                sender_email=sender_email,
                error_code=header_error,
            )

        if not parsed.rows:
            return self._build_file_rejection(
                file_name=filename,
                sender_email=sender_email,
                error_code=ValidationErrorCode.EMPTY_FILE,
            )

        if len(parsed.rows) > settings.NAT_MAX_BATCH_ROWS:
            return self._build_file_rejection(
                file_name=filename,
                sender_email=sender_email,
                error_code=ValidationErrorCode.TOO_MANY_ROWS,
            )

        validated_internal: list[ValidatedRow] = []
        row_errors: list[RowErrorResponse] = []

        for row_index, parsed_row in enumerate(parsed.rows):
            outcome = validate_row(
                parsed_row.values,
                parsed_row.raw_field_count,
                row_index,
            )
            for error in outcome.errors:
                row_errors.append(
                    RowErrorResponse(
                        row_number=error.row_number,
                        error_code=error.error_code,
                        column=error.column,
                    )
                )
                logger.warning(
                    'Row validation failed: sender_email={} file_name={} row_number={} error_code={} column={}',
                    sender_email,
                    filename,
                    error.row_number,
                    error.error_code.value,
                    error.column.value if error.column else None,
                )

            if outcome.validated_row is not None:
                validated_internal.append(outcome.validated_row)

        deduplication_outcome = await deduplicate_rows(validated_internal, uow)

        for dedup_error in deduplication_outcome.errors:
            row_errors.append(
                RowErrorResponse(
                    row_number=dedup_error.row_number,
                    error_code=dedup_error.error_code,
                    column=None,
                )
            )
            logger.warning(
                'Duplicate row detected: sender_email={} file_name={} row_number={} error_code={}',
                sender_email,
                filename,
                dedup_error.row_number,
                dedup_error.error_code.value,
            )

        validated_rows = [
            self._to_validated_row_response(row)
            for row in deduplication_outcome.accepted_rows
        ]

        total_data_rows = len(parsed.rows)
        valid_rows = len(validated_rows)
        rejected_rows = total_data_rows - valid_rows

        if rejected_rows == 0:
            status = IntakeStatus.ACCEPTED
        else:
            status = IntakeStatus.PARTIALLY_ACCEPTED

        return IntakeResponse(
            status=status,
            file_name=filename,
            sender_email=sender_email,
            total_data_rows=total_data_rows,
            valid_rows=valid_rows,
            rejected_rows=rejected_rows,
            file_errors=[],
            row_errors=row_errors,
            validated_rows=validated_rows,
        )

    def _to_validated_row_response(
        self, validated_row: ValidatedRow
    ) -> ValidatedRowResponse:
        return ValidatedRowResponse(
            row_number=validated_row.row_number,
            date_from=validated_row.date_from,
            date_to=validated_row.date_to,
            internal_ip=validated_row.internal_ip,
            external_ip=validated_row.external_ip,
            resource_ip=validated_row.resource_ip,
            region=validated_row.region,
        )

    def _build_file_rejection(
        self,
        *,
        file_name: str,
        sender_email: EmailStr,
        error_code: ValidationErrorCode,
    ) -> IntakeResponse:
        logger.warning(
            'File rejected: sender_email={} file_name={} error_code={}',
            sender_email,
            file_name,
            error_code.value,
        )
        return IntakeResponse(
            status=IntakeStatus.REJECTED,
            file_name=file_name,
            sender_email=sender_email,
            total_data_rows=0,
            valid_rows=0,
            rejected_rows=0,
            file_errors=[FileErrorResponse(error_code=error_code)],
            row_errors=[],
            validated_rows=[],
        )


intake_service = IntakeService()
