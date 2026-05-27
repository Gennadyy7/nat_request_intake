from uuid import uuid4

from pydantic import EmailStr

from app.core.config import settings
from app.core.logging import get_logger
from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.constants import IntakeStatus, ValidationErrorCode
from app.features.nat.domain.transformed_row import TransformedRow
from app.features.nat.domain.validated_row import ValidatedRow
from app.features.nat.schemas.intake import (
    FileErrorResponse,
    IntakeResponse,
    RowErrorResponse,
    TransformedRowResponse,
)
from app.features.nat.services.deduplication.deduplication_service import (
    DeduplicationService,
)
from app.features.nat.services.file_gate import (
    validate_extension,
    validate_filename,
    validate_non_empty_content,
)
from app.features.nat.services.file_parser import parse_file_content
from app.features.nat.services.header_validator import validate_headers
from app.features.nat.services.persistence.batch_persistence import (
    BatchPersistenceService,
)
from app.features.nat.services.persistence.file_storage import FileStorageService
from app.features.nat.services.row_validator import validate_row
from app.features.nat.services.transformation.transformation_service import (
    TransformationService,
)

logger = get_logger(__name__)


class IntakeService:
    def __init__(
        self,
        uow: UnitOfWorkProtocol,
        deduplication_service: DeduplicationService,
        transformation_service: TransformationService,
        file_storage_service: FileStorageService,
        batch_persistence_service: BatchPersistenceService,
    ) -> None:
        self._uow = uow
        self._deduplication = deduplication_service
        self._transformation = transformation_service
        self._file_storage = file_storage_service
        self._batch_persistence = batch_persistence_service

    async def process(
        self,
        *,
        filename: str | None,
        content: bytes,
        sender_email: EmailStr,
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

        total_data_rows = len(parsed.rows)

        if total_data_rows > settings.NAT_MAX_BATCH_ROWS:
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

        if not validated_internal:
            return await self._reject_no_valid_rows(
                file_name=filename,
                sender_email=sender_email,
                total_data_rows=total_data_rows,
                row_errors=row_errors,
            )

        deduplication_outcome = await self._deduplication.deduplicate(
            validated_internal
        )

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

        if not deduplication_outcome.accepted_rows:
            return await self._reject_no_valid_rows(
                file_name=filename,
                sender_email=sender_email,
                total_data_rows=total_data_rows,
                row_errors=row_errors,
            )

        transformed_rows: list[TransformedRow] = []

        for validated_row in deduplication_outcome.accepted_rows:
            transform_outcome = self._transformation.transform(validated_row)
            if transform_outcome.error is not None:
                transform_error = transform_outcome.error
                row_errors.append(
                    RowErrorResponse(
                        row_number=transform_error.row_number,
                        error_code=transform_error.error_code,
                        column=transform_error.column,
                    )
                )
                logger.warning(
                    'Row transformation failed: sender_email={} file_name={} row_number={} error_code={} column={}',
                    sender_email,
                    filename,
                    transform_error.row_number,
                    transform_error.error_code.value,
                    transform_error.column.value if transform_error.column else None,
                )
                continue
            transformed_rows.extend(transform_outcome.rows)

        if not transformed_rows:
            return await self._reject_no_valid_rows(
                file_name=filename,
                sender_email=sender_email,
                total_data_rows=total_data_rows,
                row_errors=row_errors,
            )

        batch_id = uuid4()
        storage_path = self._file_storage.build_storage_path(
            original_filename=filename,
            batch_id=batch_id,
        )

        try:
            await self._file_storage.save(content=content, storage_path=storage_path)
            await self._batch_persistence.persist(
                batch_id=batch_id,
                storage_path=storage_path,
                row_count=total_data_rows,
                sender_email=sender_email,
                transformed_rows=transformed_rows,
            )
            await self._uow.commit()
        except Exception:
            self._file_storage.delete(storage_path)
            await self._uow.rollback()
            logger.exception(
                'Failed to persist intake batch: sender_email={} file_name={} batch_id={}',
                sender_email,
                filename,
                batch_id,
            )
            raise

        accepted_source_rows = {row.source_row_number for row in transformed_rows}
        valid_rows = len(transformed_rows)
        rejected_rows = total_data_rows - len(accepted_source_rows)
        status = (
            IntakeStatus.ACCEPTED if not row_errors else IntakeStatus.PARTIALLY_ACCEPTED
        )

        return IntakeResponse(
            status=status,
            file_name=filename,
            sender_email=sender_email,
            batch_id=batch_id,
            total_data_rows=total_data_rows,
            valid_rows=valid_rows,
            rejected_rows=rejected_rows,
            file_errors=[],
            row_errors=row_errors,
            validated_rows=[
                self._to_transformed_row_response(row) for row in transformed_rows
            ],
        )

    async def _reject_no_valid_rows(
        self,
        *,
        file_name: str,
        sender_email: EmailStr,
        total_data_rows: int,
        row_errors: list[RowErrorResponse],
    ) -> IntakeResponse:
        await self._uow.rollback()
        logger.warning(
            'File rejected: no valid rows remained after processing: sender_email={} file_name={}',
            sender_email,
            file_name,
        )
        return IntakeResponse(
            status=IntakeStatus.REJECTED,
            file_name=file_name,
            sender_email=sender_email,
            batch_id=None,
            total_data_rows=total_data_rows,
            valid_rows=0,
            rejected_rows=total_data_rows,
            file_errors=[
                FileErrorResponse(error_code=ValidationErrorCode.NO_VALID_ROWS)
            ],
            row_errors=row_errors,
            validated_rows=[],
        )

    def _to_transformed_row_response(
        self, row: TransformedRow
    ) -> TransformedRowResponse:
        return TransformedRowResponse(
            row_number=row.source_row_number,
            datetime_from=row.datetime_from,
            datetime_to=row.datetime_to,
            src_xlated=row.src_xlated,
            src_port_xlated=row.src_port_xlated,
            src=row.src,
            src_port=row.src_port,
            dst=row.dst,
            dst_port=row.dst_port,
            region=row.region,
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
            batch_id=None,
            total_data_rows=0,
            valid_rows=0,
            rejected_rows=0,
            file_errors=[FileErrorResponse(error_code=error_code)],
            row_errors=[],
            validated_rows=[],
        )
