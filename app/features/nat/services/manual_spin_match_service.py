from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import EmailStr

from app.core.logging import get_logger
from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.constants import (
    AllowedFileExtension,
    IntakeSource,
    IntakeStatus,
    NatResultProcessingStatus,
    NatTaskStatus,
    ValidationErrorCode,
)
from app.features.nat.messages import get_message
from app.features.nat.models import (
    NatBatch,
    NatIntake,
    NatResultProcessingTask,
    NatTask,
)
from app.features.nat.schemas.intake import IntakeResponse
from app.features.nat.schemas.manual_spin import ManualSpinMatchResponse
from app.features.nat.services.intake.file_gate import (
    validate_filename,
    validate_non_empty_content,
)
from app.features.nat.services.manual_spin_match_client import (
    MatchSpinClient,
    MatchSpinFailure,
)
from app.features.nat.services.parsing.file_parser import resolve_extension
from app.features.nat.services.persistence.file_storage import FileStorageService

logger = get_logger(__name__)

_PLACEHOLDER_DATETIME = datetime(1970, 1, 1, tzinfo=UTC)
_PLACEHOLDER_IP = '0.0.0.0'
_PLACEHOLDER_REGION = '0'
_PLACEHOLDER_ERROR = 'SPIN_ONLY_MANUAL_UPLOAD'


@dataclass(frozen=True, slots=True)
class ManualSpinAccepted:
    response: ManualSpinMatchResponse


@dataclass(frozen=True, slots=True)
class ManualSpinRejected:
    response: IntakeResponse


@dataclass(frozen=True, slots=True)
class ManualSpinUpstreamFailure:
    message: str
    unavailable: bool
    intake_id: UUID
    batch_id: UUID
    result_processing_id: UUID


ManualSpinResult = ManualSpinAccepted | ManualSpinRejected | ManualSpinUpstreamFailure


class ManualSpinMatchService:
    def __init__(
        self,
        *,
        uow: UnitOfWorkProtocol,
        file_storage: FileStorageService,
        match_spin_client: MatchSpinClient,
    ) -> None:
        self._uow = uow
        self._file_storage = file_storage
        self._match_spin_client = match_spin_client

    async def process(
        self,
        *,
        filename: str | None,
        content: bytes,
        sender_email: EmailStr,
        single_stage_only: bool = False,
    ) -> ManualSpinResult:
        intake = await self._create_intake(
            sender_email=sender_email,
            file_name=filename or '',
        )

        validation_error = self._validate_file(filename=filename, content=content)
        if validation_error is not None:
            return ManualSpinRejected(
                response=await self._reject(
                    intake,
                    sender_email=sender_email,
                    error_code=validation_error,
                ),
            )

        assert filename is not None
        batch_id = uuid4()
        result_processing_id = uuid4()
        storage_path = self._file_storage.build_storage_path(
            original_filename=filename,
            batch_id=batch_id,
        )

        try:
            await self._file_storage.save(content=content, storage_path=storage_path)
            await self._create_processing_tree(
                intake=intake,
                batch_id=batch_id,
                result_processing_id=result_processing_id,
                storage_path=storage_path,
                single_stage_only=single_stage_only,
            )
            await self._uow.commit()
        except Exception:
            self._file_storage.delete(storage_path)
            logger.exception(
                'Failed to persist manual SPIN upload: intake_id={} batch_id={}',
                intake.id,
                batch_id,
            )
            raise

        match_result = await self._match_spin_client.match(batch_id)
        if isinstance(match_result, MatchSpinFailure):
            logger.error(
                'Manual SPIN notification failed: intake_id={} batch_id={} error={}',
                intake.id,
                batch_id,
                match_result.message,
            )
            return ManualSpinUpstreamFailure(
                message=match_result.message,
                unavailable=match_result.unavailable,
                intake_id=intake.id,
                batch_id=batch_id,
                result_processing_id=result_processing_id,
            )

        # SPIN is notified before pause is committed; ASSOMI enqueue checks pause only,
        # so a very fast aggregation could start the next stage in that narrow window.
        await self._uow.nat_batches.mark_notified(batch_id)
        if single_stage_only:
            await self._uow.nat_batches.set_processing_paused(batch_id, paused=True)
        await self._uow.commit()
        return ManualSpinAccepted(
            response=ManualSpinMatchResponse(
                intake_id=intake.id,
                intake_number=intake.number,
                batch_id=batch_id,
                result_processing_id=result_processing_id,
                file_name=filename,
            ),
        )

    def _validate_file(
        self,
        *,
        filename: str | None,
        content: bytes,
    ) -> ValidationErrorCode | None:
        filename_error = validate_filename(filename)
        if filename_error is not None:
            return filename_error
        assert filename is not None
        if resolve_extension(filename) != AllowedFileExtension.CSV:
            return ValidationErrorCode.MANUAL_SPIN_CSV_REQUIRED
        return validate_non_empty_content(content)

    async def _create_intake(
        self,
        *,
        sender_email: EmailStr,
        file_name: str,
    ) -> NatIntake:
        return await self._uow.nat_intakes.create(
            NatIntake(
                id=uuid4(),
                sender_email=str(sender_email),
                file_name=file_name,
                status=IntakeStatus.REJECTED.value,
                source=IntakeSource.MANUAL_SPIN.value,
                error_code=None,
            )
        )

    async def _reject(
        self,
        intake: NatIntake,
        *,
        sender_email: EmailStr,
        error_code: ValidationErrorCode,
    ) -> IntakeResponse:
        intake.error_code = error_code.value
        await self._uow.commit()
        return IntakeResponse(
            intake_id=intake.id,
            number=intake.number,
            batch_id=None,
            status=IntakeStatus.REJECTED,
            source=IntakeSource.MANUAL_SPIN,
            file_name=intake.file_name,
            sender_email=sender_email,
            total_data_rows=0,
            valid_rows=0,
            rejected_rows=0,
            code=error_code,
            message=get_message(error_code),
        )

    async def _create_processing_tree(
        self,
        *,
        intake: NatIntake,
        batch_id: UUID,
        result_processing_id: UUID,
        storage_path: str,
        single_stage_only: bool = False,
    ) -> None:
        intake.status = IntakeStatus.ACCEPTED.value
        batch = NatBatch(
            id=batch_id,
            intake_id=intake.id,
            file_name=storage_path,
            row_count=0,
            single_stage_only=single_stage_only,
        )
        await self._uow.nat_batches.create(batch)
        await self._uow.nat_tasks.create(
            NatTask(
                id=uuid4(),
                batch_id=batch_id,
                datetime_from=_PLACEHOLDER_DATETIME,
                datetime_to=_PLACEHOLDER_DATETIME,
                src_xlated=_PLACEHOLDER_IP,
                src_port_xlated=None,
                src=_PLACEHOLDER_IP,
                src_port=None,
                dst=_PLACEHOLDER_IP,
                dst_port=None,
                region=_PLACEHOLDER_REGION,
                status=NatTaskStatus.LOCAL_ABANDONED,
                error_message=_PLACEHOLDER_ERROR,
            )
        )
        await self._uow.nat_result_processing_tasks.create(
            NatResultProcessingTask(
                id=result_processing_id,
                nat_batch_id=batch_id,
                status=NatResultProcessingStatus.PENDING.value,
                output_files=[
                    {
                        'index': 1,
                        'aggregated_path': storage_path,
                        'spin_matched_path': None,
                    }
                ],
                total_lines=0,
                matched_count=0,
                total_to_match=None,
            )
        )
