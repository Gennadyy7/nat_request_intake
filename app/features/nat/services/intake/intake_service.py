from collections.abc import Sequence
from uuid import UUID, uuid4

from pydantic import EmailStr

from app.core.config import settings
from app.core.logging import get_logger
from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.constants import IntakeStatus, RowErrorCode, ValidationErrorCode
from app.features.nat.domain.transformed_row import TransformedRow
from app.features.nat.domain.validated_row import ValidatedRow
from app.features.nat.messages import get_message
from app.features.nat.models import NatIntake, NatIntakeRowError
from app.features.nat.schemas.intake import IntakeResponse, RowErrorResponse
from app.features.nat.services.deduplication.deduplication_service import (
    DeduplicationService,
)
from app.features.nat.services.intake.file_gate import (
    validate_extension,
    validate_filename,
    validate_non_empty_content,
)
from app.features.nat.services.parsing.file_parser import parse_file_content
from app.features.nat.services.persistence.batch_persistence import (
    BatchPersistenceService,
)
from app.features.nat.services.persistence.file_storage import FileStorageService
from app.features.nat.services.transformation.transformation_service import (
    TransformationService,
)
from app.features.nat.services.validation.header_validator import validate_headers
from app.features.nat.services.validation.row_validator import validate_row

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
        display_file_name = filename or ''
        intake = await self._create_intake(
            sender_email=sender_email,
            file_name=display_file_name,
        )

        filename_error = validate_filename(filename)
        if filename_error is not None:
            return await self._reject_file(
                intake,
                sender_email=sender_email,
                error_code=filename_error,
            )

        assert filename is not None
        intake.file_name = filename

        extension, extension_error = validate_extension(filename)
        if extension_error is not None:
            return await self._reject_file(
                intake,
                sender_email=sender_email,
                error_code=extension_error,
            )

        assert extension is not None

        empty_error = validate_non_empty_content(content)
        if empty_error is not None:
            return await self._reject_file(
                intake,
                sender_email=sender_email,
                error_code=empty_error,
            )

        parsed = parse_file_content(content, extension)

        if not parsed.headers and not parsed.rows:
            return await self._reject_file(
                intake,
                sender_email=sender_email,
                error_code=ValidationErrorCode.EMPTY_FILE,
            )

        header_error = validate_headers(parsed.headers)
        if header_error is not None:
            return await self._reject_file(
                intake,
                sender_email=sender_email,
                error_code=header_error,
            )

        if not parsed.rows:
            return await self._reject_file(
                intake,
                sender_email=sender_email,
                error_code=ValidationErrorCode.EMPTY_FILE,
            )

        total_data_rows = len(parsed.rows)

        if total_data_rows > settings.NAT_MAX_BATCH_ROWS:
            return await self._reject_file(
                intake,
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
                        code=error.error_code,
                        column=error.column,
                        message=get_message(error.error_code),
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
            return await self._reject_with_row_errors(
                intake,
                sender_email=sender_email,
                total_data_rows=total_data_rows,
                row_errors=row_errors,
            )

        deduplication_outcome = await self._deduplication.check_duplicates(
            validated_internal
        )

        for dedup_error in deduplication_outcome.errors:
            row_errors.append(
                RowErrorResponse(
                    row_number=dedup_error.row_number,
                    code=dedup_error.error_code,
                    column=None,
                    message=get_message(dedup_error.error_code),
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
            return await self._reject_with_row_errors(
                intake,
                sender_email=sender_email,
                total_data_rows=total_data_rows,
                row_errors=row_errors,
            )

        transformed_rows: list[TransformedRow] = []
        transformed_validated_rows: list[ValidatedRow] = []

        for validated_row in deduplication_outcome.accepted_rows:
            transform_outcome = self._transformation.transform(validated_row)
            if transform_outcome.error is not None:
                transform_error = transform_outcome.error
                row_errors.append(
                    RowErrorResponse(
                        row_number=transform_error.row_number,
                        code=transform_error.error_code,
                        column=transform_error.column,
                        message=get_message(transform_error.error_code),
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
            transformed_validated_rows.append(validated_row)
            transformed_rows.extend(transform_outcome.rows)

        if not transformed_rows:
            return await self._reject_with_row_errors(
                intake,
                sender_email=sender_email,
                total_data_rows=total_data_rows,
                row_errors=row_errors,
            )

        registration_outcome = await self._deduplication.register_accepted_rows(
            transformed_validated_rows
        )

        for registration_error in registration_outcome.errors:
            row_errors.append(
                RowErrorResponse(
                    row_number=registration_error.row_number,
                    code=registration_error.error_code,
                    column=None,
                    message=get_message(registration_error.error_code),
                )
            )
            logger.warning(
                'Duplicate row detected at registration: sender_email={} file_name={} row_number={} error_code={}',
                sender_email,
                filename,
                registration_error.row_number,
                registration_error.error_code.value,
            )

        if not registration_outcome.registered_rows:
            return await self._reject_with_row_errors(
                intake,
                sender_email=sender_email,
                total_data_rows=total_data_rows,
                row_errors=row_errors,
            )

        registered_row_numbers = {
            row.row_number for row in registration_outcome.registered_rows
        }
        transformed_rows = [
            row
            for row in transformed_rows
            if row.source_row_number in registered_row_numbers
        ]

        batch_id = uuid4()
        storage_path = self._file_storage.build_storage_path(
            original_filename=filename,
            batch_id=batch_id,
        )

        try:
            await self._file_storage.save(content=content, storage_path=storage_path)
            await self._batch_persistence.persist(
                intake_id=intake.id,
                batch_id=batch_id,
                storage_path=storage_path,
                row_count=total_data_rows,
                transformed_rows=transformed_rows,
            )
            if row_errors:
                await self._persist_row_errors(intake.id, row_errors)
            intake.status = (
                IntakeStatus.ACCEPTED.value
                if not row_errors
                else IntakeStatus.PARTIALLY_ACCEPTED.value
            )
            intake.error_code = None
            await self._uow.commit()
        except Exception:
            self._file_storage.delete(storage_path)
            logger.exception(
                'Failed to persist intake batch: sender_email={} file_name={} intake_id={} batch_id={}',
                sender_email,
                filename,
                intake.id,
                batch_id,
            )
            raise

        accepted_source_rows = {row.source_row_number for row in transformed_rows}
        valid_rows = len(transformed_rows)
        rejected_rows = total_data_rows - len(accepted_source_rows)
        status = (
            IntakeStatus.ACCEPTED if not row_errors else IntakeStatus.PARTIALLY_ACCEPTED
        )

        return self._build_response(
            intake_id=intake.id,
            status=status,
            file_name=filename,
            sender_email=sender_email,
            batch_id=batch_id,
            total_data_rows=total_data_rows,
            valid_rows=valid_rows,
            rejected_rows=rejected_rows,
            error_code=None,
        )

    async def _create_intake(
        self,
        *,
        sender_email: EmailStr,
        file_name: str,
    ) -> NatIntake:
        intake = NatIntake(
            id=uuid4(),
            sender_email=str(sender_email),
            file_name=file_name,
            status=IntakeStatus.REJECTED.value,
            error_code=None,
        )
        await self._uow.nat_intakes.create(intake)
        return intake

    async def _persist_row_errors(
        self,
        intake_id: UUID,
        row_errors: Sequence[RowErrorResponse],
    ) -> None:
        if not row_errors:
            return
        entities = [
            NatIntakeRowError(
                id=uuid4(),
                intake_id=intake_id,
                row_number=error.row_number,
                error_code=_row_error_code_value(error.code),
                column=error.column.value if error.column is not None else None,
            )
            for error in row_errors
        ]
        await self._uow.nat_intake_row_errors.create_many(entities)

    async def _reject_file(
        self,
        intake: NatIntake,
        *,
        sender_email: EmailStr,
        error_code: ValidationErrorCode,
    ) -> IntakeResponse:
        logger.warning(
            'File rejected: sender_email={} file_name={} error_code={}',
            sender_email,
            intake.file_name,
            error_code.value,
        )
        intake.status = IntakeStatus.REJECTED.value
        intake.error_code = error_code.value
        await self._uow.commit()
        return self._build_response(
            intake_id=intake.id,
            status=IntakeStatus.REJECTED,
            file_name=intake.file_name,
            sender_email=sender_email,
            batch_id=None,
            total_data_rows=0,
            valid_rows=0,
            rejected_rows=0,
            error_code=error_code,
        )

    async def _reject_with_row_errors(
        self,
        intake: NatIntake,
        *,
        sender_email: EmailStr,
        total_data_rows: int,
        row_errors: list[RowErrorResponse],
    ) -> IntakeResponse:
        logger.warning(
            'File rejected: no valid rows remained after processing: sender_email={} file_name={}',
            sender_email,
            intake.file_name,
        )
        intake.status = IntakeStatus.REJECTED.value
        intake.error_code = ValidationErrorCode.NO_VALID_ROWS.value
        await self._persist_row_errors(intake.id, row_errors)
        await self._uow.commit()
        return self._build_response(
            intake_id=intake.id,
            status=IntakeStatus.REJECTED,
            file_name=intake.file_name,
            sender_email=sender_email,
            batch_id=None,
            total_data_rows=total_data_rows,
            valid_rows=0,
            rejected_rows=total_data_rows,
            error_code=ValidationErrorCode.NO_VALID_ROWS,
        )

    def _build_response(
        self,
        *,
        intake_id: UUID,
        status: IntakeStatus,
        file_name: str,
        sender_email: EmailStr,
        batch_id: UUID | None,
        total_data_rows: int,
        valid_rows: int,
        rejected_rows: int,
        error_code: ValidationErrorCode | None,
    ) -> IntakeResponse:
        return IntakeResponse(
            intake_id=intake_id,
            batch_id=batch_id,
            status=status,
            file_name=file_name,
            sender_email=sender_email,
            total_data_rows=total_data_rows,
            valid_rows=valid_rows,
            rejected_rows=rejected_rows,
            code=error_code,
            message=get_message(error_code) if error_code is not None else None,
        )


def _row_error_code_value(error_code: RowErrorCode) -> str:
    return error_code.value
