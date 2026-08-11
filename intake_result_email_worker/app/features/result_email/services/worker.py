import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.features.assomi.models import AssomiTask
from app.features.nat.models import NatBatch, NatIntake, NatResultProcessingTask
from app.features.nat.services.persistence.file_storage import FileStorageService
from app.features.nat.services.results.builder import build_intake_results_xlsx_path
from app.features.nat.services.results.sheet_plan import (
    ResultFileStorages,
    build_download_filename,
)
from intake_result_email_worker.app.core.config import settings
from intake_result_email_worker.app.core.logging import get_logger
from intake_result_email_worker.app.core.unit_of_work import unit_of_work
from intake_result_email_worker.app.features.result_email.artifact import (
    ArtifactStatus,
    resolve_assomi_artifact,
)
from intake_result_email_worker.app.features.result_email.classification import (
    ResultEmailClassification,
    ResultEmailContext,
    build_context,
    classify_pipeline_outcome,
)
from intake_result_email_worker.app.features.result_email.composer import (
    AttachmentKind,
    build_result_email_message,
)
from intake_result_email_worker.app.features.result_email.constants import (
    IntakeResultEmailAttachment,
)
from intake_result_email_worker.app.features.result_email.messages import (
    ASSOMI_FILE_MISSING_REASON,
)
from intake_result_email_worker.app.features.result_email.smtp.client import (
    SmtpClientError,
    SmtpMailClient,
)

logger = get_logger(__name__)

SendOutcome = Literal['sent', 'smtp_failure', 'skipped']


@dataclass(frozen=True, slots=True)
class WorkerCycleStats:
    sent: int = 0
    smtp_failures: int = 0
    skipped: int = 0


@dataclass(frozen=True, slots=True)
class _PreparedEmail:
    context: ResultEmailContext
    classification: ResultEmailClassification
    attachment_bytes: bytes | None
    attachment_filename: str | None
    attachment_kind: AttachmentKind | None
    oversized_limit_bytes: int | None


class IntakeResultEmailWorkerService:
    async def run_once(self) -> WorkerCycleStats:
        if not settings.INTAKE_RESULT_EMAIL_ENABLED:
            logger.debug('Intake result email worker skipped: disabled by config')
            return WorkerCycleStats()

        logger.info('Intake result email worker cycle started')
        batch_limit = self._batch_limit()
        sent = 0
        smtp_failures = 0
        skipped = 0
        processed = 0
        while True:
            if batch_limit is not None and processed >= batch_limit:
                break
            outcome = await self._process_one_batch()
            if outcome is None:
                break
            processed += 1
            match outcome:
                case 'sent':
                    sent += 1
                case 'smtp_failure':
                    smtp_failures += 1
                case 'skipped':
                    skipped += 1
        stats = WorkerCycleStats(
            sent=sent,
            smtp_failures=smtp_failures,
            skipped=skipped,
        )
        logger.info(
            'Intake result email worker cycle finished: '
            'sent={} smtp_failures={} skipped={}',
            stats.sent,
            stats.smtp_failures,
            stats.skipped,
        )
        return stats

    def _batch_limit(self) -> int | None:
        if settings.INTAKE_RESULT_EMAIL_WORKER_PROCESS_ALL:
            return None
        return settings.INTAKE_RESULT_EMAIL_WORKER_BATCH_LIMIT

    async def _process_one_batch(self) -> SendOutcome | None:
        async with unit_of_work() as uow:
            batches = await uow.nat_batches.claim_for_result_email(
                1,
                respect_processing_pause=(
                    settings.INTAKE_RESULT_EMAIL_RESPECT_PROCESSING_PAUSE
                ),
            )
            if not batches:
                return None
            batch = batches[0]
            intake = await uow.nat_intakes.get_by_id(batch.intake_id)
            if intake is None:
                logger.error(
                    'Result email skipped: intake missing for batch_id={}',
                    batch.id,
                )
                return 'skipped'

            email_message = await uow.email_messages.get_by_nat_intake_id(intake.id)
            assomi_task = await uow.assomi_tasks.get_by_nat_batch_id(batch.id)
            aggregation_task = await uow.nat_result_processing_tasks.get_by_batch_id(
                batch.id,
            )
            nat_tasks = await uow.nat_tasks.list_by_batch_id(batch.id)

            context = build_context(
                intake=intake,
                batch_id=batch.id,
                original_subject=(
                    email_message.subject if email_message is not None else None
                ),
                original_message_id=(
                    email_message.message_id if email_message is not None else None
                ),
            )
            classification = classify_pipeline_outcome(
                source=context.source,
                assomi_task=assomi_task,
                aggregation_task=aggregation_task,
                nat_tasks=nat_tasks,
            )
            if classification is None:
                logger.warning(
                    'Result email skipped: batch claimed but not terminal batch_id={}',
                    batch.id,
                )
                return 'skipped'

            prepared = await self._prepare_email(
                context=context,
                classification=classification,
                intake=intake,
                batch=batch,
                assomi_task=assomi_task,
                aggregation_task=aggregation_task,
            )
            mime_message = build_result_email_message(
                context=prepared.context,
                classification=prepared.classification,
                from_addr=settings.IMAP_USER,
                reply_to=str(settings.EMAIL_REPLY_TO),
                attachment_bytes=prepared.attachment_bytes,
                attachment_filename=prepared.attachment_filename,
                attachment_kind=prepared.attachment_kind,
                oversized_limit_bytes=prepared.oversized_limit_bytes,
            )
            try:
                async with SmtpMailClient() as smtp:
                    await smtp.send_message(mime_message)
            except SmtpClientError:
                logger.exception(
                    'Failed to send result email: batch_id={} intake_id={} '
                    'recipient={}',
                    batch.id,
                    context.intake_id,
                    context.sender_email,
                )
                return 'smtp_failure'

            await uow.nat_batches.mark_result_emailed(batch.id)
            await uow.commit()
            logger.info(
                'Result email sent: batch_id={} intake_id={} kind={} recipient={}',
                batch.id,
                context.intake_id,
                prepared.classification.kind,
                context.sender_email,
            )
            return 'sent'

    async def _prepare_email(
        self,
        *,
        context: ResultEmailContext,
        classification: ResultEmailClassification,
        intake: NatIntake,
        batch: NatBatch,
        assomi_task: AssomiTask | None,
        aggregation_task: NatResultProcessingTask | None,
    ) -> _PreparedEmail:
        if classification.kind != 'success':
            return _PreparedEmail(
                context=context,
                classification=classification,
                attachment_bytes=None,
                attachment_filename=None,
                attachment_kind=None,
                oversized_limit_bytes=None,
            )

        if (
            settings.INTAKE_RESULT_EMAIL_ATTACHMENT
            == IntakeResultEmailAttachment.COMBINED_XLSX
        ):
            return await self._prepare_combined_xlsx_email(
                context=context,
                classification=classification,
                intake=intake,
                batch=batch,
                assomi_task=assomi_task,
                aggregation_task=aggregation_task,
            )

        artifact = resolve_assomi_artifact(
            classification.output_path,
            base_dir=settings.ASSOMI_BASE_DIR,
            max_attachment_bytes=settings.INTAKE_RESULT_EMAIL_MAX_ATTACHMENT_BYTES,
        )
        match artifact.status:
            case ArtifactStatus.MISSING:
                return _PreparedEmail(
                    context=context,
                    classification=ResultEmailClassification(
                        kind='failure',
                        stage='assomi',
                        reason=ASSOMI_FILE_MISSING_REASON,
                    ),
                    attachment_bytes=None,
                    attachment_filename=None,
                    attachment_kind=None,
                    oversized_limit_bytes=None,
                )
            case ArtifactStatus.OVERSIZED:
                return _PreparedEmail(
                    context=context,
                    classification=ResultEmailClassification(
                        kind='success_oversized',
                        found_count=classification.found_count,
                        missing_count=classification.missing_count,
                        output_path=classification.output_path,
                    ),
                    attachment_bytes=None,
                    attachment_filename=None,
                    attachment_kind=None,
                    oversized_limit_bytes=(
                        settings.INTAKE_RESULT_EMAIL_MAX_ATTACHMENT_BYTES
                    ),
                )
            case ArtifactStatus.OK:
                assert artifact.path is not None
                assert artifact.filename is not None
                content = await _read_file_bytes(artifact.path)
                return _PreparedEmail(
                    context=context,
                    classification=classification,
                    attachment_bytes=content,
                    attachment_filename=artifact.filename,
                    attachment_kind=IntakeResultEmailAttachment.ASSOMI_CSV.value,
                    oversized_limit_bytes=None,
                )

    async def _prepare_combined_xlsx_email(
        self,
        *,
        context: ResultEmailContext,
        classification: ResultEmailClassification,
        intake: NatIntake,
        batch: NatBatch,
        assomi_task: AssomiTask | None,
        aggregation_task: NatResultProcessingTask | None,
    ) -> _PreparedEmail:
        nat_upload_base_dir = settings.NAT_UPLOAD_BASE_DIR
        spin_aggregated_base_dir = settings.SPIN_AGGREGATED_BASE_DIR
        merge_stage_files = settings.NAT_RESULT_XLSX_MERGE_STAGE_FILES
        if (
            nat_upload_base_dir is None
            or spin_aggregated_base_dir is None
            or merge_stage_files is None
        ):
            raise RuntimeError(
                'combined_xlsx attachment requires NAT_UPLOAD_BASE_DIR, '
                'SPIN_AGGREGATED_BASE_DIR, and NAT_RESULT_XLSX_MERGE_STAGE_FILES'
            )

        storages = ResultFileStorages(
            nat_upload=FileStorageService(base_dir=nat_upload_base_dir),
            spin=FileStorageService(
                base_dir=spin_aggregated_base_dir,
                use_date_subdirectory=False,
            ),
            assomi=FileStorageService(
                base_dir=settings.ASSOMI_BASE_DIR,
                use_date_subdirectory=False,
            ),
        )
        xlsx_path = await build_intake_results_xlsx_path(
            intake=intake,
            batch=batch,
            assomi_task=assomi_task,
            aggregation_task=aggregation_task,
            storages=storages,
            merge_stage_files=merge_stage_files,
        )
        try:
            content = await _read_file_bytes(xlsx_path)
        finally:
            xlsx_path.unlink(missing_ok=True)

        attachment_filename = build_download_filename(
            intake_number=int(intake.number),
        )
        if len(content) > settings.INTAKE_RESULT_EMAIL_MAX_ATTACHMENT_BYTES:
            return _PreparedEmail(
                context=context,
                classification=ResultEmailClassification(
                    kind='success_oversized',
                    found_count=classification.found_count,
                    missing_count=classification.missing_count,
                    output_path=classification.output_path,
                ),
                attachment_bytes=None,
                attachment_filename=None,
                attachment_kind=None,
                oversized_limit_bytes=settings.INTAKE_RESULT_EMAIL_MAX_ATTACHMENT_BYTES,
            )

        return _PreparedEmail(
            context=context,
            classification=classification,
            attachment_bytes=content,
            attachment_filename=attachment_filename,
            attachment_kind=IntakeResultEmailAttachment.COMBINED_XLSX.value,
            oversized_limit_bytes=None,
        )


async def _read_file_bytes(path: Path) -> bytes:
    return await asyncio.to_thread(path.read_bytes)
