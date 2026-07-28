from dataclasses import dataclass
from typing import Literal

from assomi_worker.app.core.config import settings
from assomi_worker.app.core.logging import get_logger
from assomi_worker.app.core.unit_of_work import unit_of_work
from assomi_worker.app.features.assomi.assomi_client import (
    AssomiClient,
    AssomiPermanentError,
    AssomiSuccess,
    AssomiTransientError,
)
from assomi_worker.app.features.assomi.csv_io import (
    build_assomi_output_path,
    build_assomi_rows,
    collect_spin_matched_paths,
    read_spin_logins_from_files,
    resolve_safe_path,
    write_assomi_csv,
)
from assomi_worker.app.features.assomi.logins import build_login_set

logger = get_logger(__name__)

AssomiOutcome = Literal['success', 'transient', 'permanent']


@dataclass(frozen=True, slots=True)
class WorkerCycleStats:
    ensured: int = 0
    completed: int = 0
    transient_errors: int = 0
    permanent_errors: int = 0


class AssomiWorkerService:
    def __init__(self, assomi_client: AssomiClient) -> None:
        self._assomi_client = assomi_client

    async def run_once(self) -> WorkerCycleStats:
        logger.info('ASSOMI worker cycle started')
        ensured = await self._ensure_pending_tasks()
        batch_limit = self._batch_limit()
        completed = 0
        transient_errors = 0
        permanent_errors = 0
        processed = 0
        while True:
            if batch_limit is not None and processed >= batch_limit:
                break
            outcome = await self._process_one_task()
            if outcome is None:
                break
            processed += 1
            match outcome:
                case 'success':
                    completed += 1
                case 'transient':
                    transient_errors += 1
                case 'permanent':
                    permanent_errors += 1
        stats = WorkerCycleStats(
            ensured=ensured,
            completed=completed,
            transient_errors=transient_errors,
            permanent_errors=permanent_errors,
        )
        logger.info(
            'ASSOMI worker cycle finished: ensured={} completed={} '
            'transient_errors={} permanent_errors={}',
            stats.ensured,
            stats.completed,
            stats.transient_errors,
            stats.permanent_errors,
        )
        return stats

    def _batch_limit(self) -> int | None:
        if settings.ASSOMI_WORKER_PROCESS_ALL:
            return None
        return settings.ASSOMI_WORKER_BATCH_LIMIT

    async def _ensure_pending_tasks(self) -> int:
        async with unit_of_work() as uow:
            ensured = (
                await uow.assomi_tasks.ensure_pending_for_completed_aggregation_tasks()
            )
            await uow.commit()
        if ensured:
            logger.info('ASSOMI tasks enqueued: count={}', ensured)
        return ensured

    async def _process_one_task(self) -> AssomiOutcome | None:
        async with unit_of_work() as uow:
            tasks = await uow.assomi_tasks.claim_for_processing(1)
            if not tasks:
                return None
            task = tasks[0]
            aggregation_task = await uow.nat_result_processing_tasks.get_by_id(
                task.aggregation_task_id,
            )
            if aggregation_task is None:
                await uow.assomi_tasks.mark_failed(
                    task.id,
                    error_message=(
                        'Aggregation task not found for ASSOMI enrichment: '
                        f'{task.aggregation_task_id}'
                    ),
                )
                await uow.commit()
                logger.error(
                    'ASSOMI permanent failure: assomi_task_id={} reason=missing_aggregation_task',
                    task.id,
                )
                return 'permanent'

            spin_paths = collect_spin_matched_paths(aggregation_task.output_files)
            if not spin_paths:
                await uow.assomi_tasks.mark_failed(
                    task.id,
                    error_message='Completed aggregation task has no spin_matched_path',
                )
                await uow.commit()
                logger.error(
                    'ASSOMI permanent failure: assomi_task_id={} reason=no_spin_matched_path',
                    task.id,
                )
                return 'permanent'

            resolved_paths = []
            for storage_path in spin_paths:
                resolved = resolve_safe_path(
                    storage_path,
                    base_dir=settings.SPIN_AGGREGATED_BASE_DIR,
                )
                if resolved is None or not resolved.is_file():
                    await uow.assomi_tasks.mark_failed(
                        task.id,
                        error_message=(
                            'spin_matched file is missing or outside base dir: '
                            f'{storage_path}'
                        ),
                    )
                    await uow.commit()
                    logger.error(
                        'ASSOMI permanent failure: assomi_task_id={} path={}',
                        task.id,
                        storage_path,
                    )
                    return 'permanent'
                resolved_paths.append(resolved)

            try:
                spin_logins = read_spin_logins_from_files(resolved_paths)
            except ValueError as exc:
                await uow.assomi_tasks.mark_failed(
                    task.id,
                    error_message=str(exc),
                )
                await uow.commit()
                logger.error(
                    'ASSOMI permanent failure: assomi_task_id={} error={}',
                    task.id,
                    exc,
                )
                return 'permanent'

            login_set = build_login_set(spin_logins)
            output_path = build_assomi_output_path(
                spin_matched_path=spin_paths[0],
                assomi_base_dir=settings.ASSOMI_BASE_DIR,
            )

            if not login_set.local_parts:
                await write_assomi_csv(output_path=output_path, rows=[])
                await uow.assomi_tasks.mark_completed(
                    task.id,
                    output_path=output_path,
                    found_count=0,
                    missing_count=0,
                )
                await uow.commit()
                logger.info(
                    'ASSOMI task completed with empty logins: assomi_task_id={} path={}',
                    task.id,
                    output_path,
                )
                return 'success'

            result = await self._assomi_client.fetch_abonents(
                list(login_set.local_parts)
            )
            if isinstance(result, AssomiTransientError):
                logger.warning(
                    'ASSOMI transient failure: assomi_task_id={} error={}',
                    task.id,
                    result.message,
                )
                return 'transient'
            if isinstance(result, AssomiPermanentError):
                await uow.assomi_tasks.mark_failed(
                    task.id,
                    error_message=result.message,
                )
                await uow.commit()
                logger.error(
                    'ASSOMI permanent failure: assomi_task_id={} error={}',
                    task.id,
                    result.message,
                )
                return 'permanent'
            if isinstance(result, AssomiSuccess):
                rows, found_count, missing_count = build_assomi_rows(
                    login_set,
                    result.abonents,
                )
                await write_assomi_csv(output_path=output_path, rows=rows)
                await uow.assomi_tasks.mark_completed(
                    task.id,
                    output_path=output_path,
                    found_count=found_count,
                    missing_count=missing_count,
                )
                await uow.commit()
                logger.info(
                    'ASSOMI task completed: assomi_task_id={} batch_id={} '
                    'found={} missing={} code_msg={} retries={} path={}',
                    task.id,
                    task.nat_batch_id,
                    found_count,
                    missing_count,
                    result.code_msg_used,
                    result.code_msg_retries,
                    output_path,
                )
                return 'success'

            logger.error(
                'ASSOMI unexpected result type: assomi_task_id={} type={}',
                task.id,
                type(result).__name__,
            )
            return 'transient'
