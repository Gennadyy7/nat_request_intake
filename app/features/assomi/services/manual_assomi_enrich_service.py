from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import EmailStr

from app.core.logging import get_logger
from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.assomi.constants import AssomiTaskStatus
from app.features.assomi.models import AssomiTask
from app.features.assomi.schemas import ManualAssomiEnrichResponse
from app.features.assomi.services.manual_assomi_file_validation import (
    validate_manual_assomi_upload,
)
from app.features.nat.constants import (
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
from app.features.nat.services.persistence.file_storage import FileStorageService

logger = get_logger(__name__)

_PLACEHOLDER_DATETIME = datetime(1970, 1, 1, tzinfo=UTC)
_PLACEHOLDER_IP = '0.0.0.0'
_PLACEHOLDER_REGION = '0'
_PLACEHOLDER_ERROR = 'ASSOMI_ONLY_MANUAL_UPLOAD'


@dataclass(frozen=True, slots=True)
class ManualAssomiAccepted:
    response: ManualAssomiEnrichResponse


@dataclass(frozen=True, slots=True)
class ManualAssomiRejected:
    response: IntakeResponse


ManualAssomiResult = ManualAssomiAccepted | ManualAssomiRejected


class ManualAssomiEnrichService:
    def __init__(
        self,
        *,
        uow: UnitOfWorkProtocol,
        file_storage: FileStorageService,
    ) -> None:
        self._uow = uow
        self._file_storage = file_storage

    async def process(
        self,
        *,
        filename: str | None,
        content: bytes,
        sender_email: EmailStr,
    ) -> ManualAssomiResult:
        intake = await self._create_intake(
            sender_email=sender_email,
            file_name=filename or '',
        )

        validation_error = validate_manual_assomi_upload(
            filename=filename,
            content=content,
        )
        if validation_error is not None:
            return ManualAssomiRejected(
                response=await self._reject(
                    intake,
                    sender_email=sender_email,
                    error_code=validation_error,
                ),
            )

        assert filename is not None
        batch_id = uuid4()
        result_processing_id = uuid4()
        assomi_task_id = uuid4()
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
                assomi_task_id=assomi_task_id,
                storage_path=storage_path,
            )
            await self._uow.commit()
        except Exception:
            self._file_storage.delete(storage_path)
            logger.exception(
                'Failed to persist manual ASSOMI upload: intake_id={} batch_id={}',
                intake.id,
                batch_id,
            )
            raise

        return ManualAssomiAccepted(
            response=ManualAssomiEnrichResponse(
                intake_id=intake.id,
                intake_number=intake.number,
                batch_id=batch_id,
                result_processing_id=result_processing_id,
                assomi_task_id=assomi_task_id,
                file_name=filename,
            ),
        )

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
                source=IntakeSource.MANUAL_ASSOMI.value,
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
            source=IntakeSource.MANUAL_ASSOMI,
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
        assomi_task_id: UUID,
        storage_path: str,
    ) -> None:
        now = datetime.now(UTC)
        intake.status = IntakeStatus.ACCEPTED.value
        batch = NatBatch(
            id=batch_id,
            intake_id=intake.id,
            file_name=storage_path,
            row_count=0,
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
                status=NatResultProcessingStatus.COMPLETED.value,
                completed_at=now,
                output_files=[
                    {
                        'index': 1,
                        'aggregated_path': None,
                        'spin_matched_path': storage_path,
                    }
                ],
                total_lines=0,
                matched_count=0,
                total_to_match=None,
            )
        )
        await self._uow.assomi_tasks.create(
            AssomiTask(
                id=assomi_task_id,
                aggregation_task_id=result_processing_id,
                nat_batch_id=batch_id,
                status=AssomiTaskStatus.PENDING.value,
            )
        )
