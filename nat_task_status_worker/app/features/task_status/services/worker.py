from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from app.core.unit_of_work.protocol import UnitOfWorkProtocol
from app.features.nat.models import NatTask, NatTaskResultFile
from nat_task_status_worker.app.core.config import settings
from nat_task_status_worker.app.core.logging import get_logger
from nat_task_status_worker.app.core.unit_of_work import unit_of_work
from nat_task_status_worker.app.features.task_status.nat_webapi_client import (
    NatWebApiClient,
    NatWebApiPermanentError,
    NatWebApiSuccess,
)
from nat_task_status_worker.app.features.task_status.schemas import (
    NatStatusResponse,
    NatWebApiFile,
)

logger = get_logger(__name__)

TaskOutcome = Literal['success', 'transient', 'permanent']


@dataclass(frozen=True, slots=True)
class WorkerCycleStats:
    dispatched: int = 0
    polled: int = 0
    dispatch_transient_errors: int = 0
    poll_transient_errors: int = 0
    dispatch_permanent_errors: int = 0
    poll_permanent_errors: int = 0


@dataclass(frozen=True, slots=True)
class _DispatchCycleStats:
    dispatched: int = 0
    dispatch_transient_errors: int = 0
    dispatch_permanent_errors: int = 0


@dataclass(frozen=True, slots=True)
class _PollCycleStats:
    polled: int = 0
    poll_transient_errors: int = 0
    poll_permanent_errors: int = 0


class NatTaskStatusWorkerService:
    def __init__(self, nat_client: NatWebApiClient) -> None:
        self._nat_client = nat_client

    async def run_once(self) -> WorkerCycleStats:
        logger.info('NAT task status worker cycle started')
        batch_limit = self._batch_limit()
        dispatch_stats = await self._process_dispatch_queue(batch_limit)
        poll_stats = await self._process_poll_queue(batch_limit)
        stats = WorkerCycleStats(
            dispatched=dispatch_stats.dispatched,
            polled=poll_stats.polled,
            dispatch_transient_errors=dispatch_stats.dispatch_transient_errors,
            poll_transient_errors=poll_stats.poll_transient_errors,
            dispatch_permanent_errors=dispatch_stats.dispatch_permanent_errors,
            poll_permanent_errors=poll_stats.poll_permanent_errors,
        )
        logger.info(
            'NAT task status worker cycle finished: dispatched={} polled={} '
            'dispatch_transient_errors={} poll_transient_errors={} '
            'dispatch_permanent_errors={} poll_permanent_errors={}',
            stats.dispatched,
            stats.polled,
            stats.dispatch_transient_errors,
            stats.poll_transient_errors,
            stats.dispatch_permanent_errors,
            stats.poll_permanent_errors,
        )
        return stats

    def _batch_limit(self) -> int | None:
        if settings.NAT_TASK_STATUS_WORKER_PROCESS_ALL_NON_TERMINAL:
            return None
        return settings.NAT_TASK_STATUS_WORKER_BATCH_LIMIT

    async def _process_dispatch_queue(
        self,
        batch_limit: int | None,
    ) -> _DispatchCycleStats:
        dispatched = 0
        dispatch_transient_errors = 0
        dispatch_permanent_errors = 0
        processed = 0
        while True:
            if batch_limit is not None and processed >= batch_limit:
                break
            outcome = await self._dispatch_one_task()
            if outcome is None:
                break
            processed += 1
            match outcome:
                case 'success':
                    dispatched += 1
                case 'transient':
                    dispatch_transient_errors += 1
                case 'permanent':
                    dispatch_permanent_errors += 1
        return _DispatchCycleStats(
            dispatched=dispatched,
            dispatch_transient_errors=dispatch_transient_errors,
            dispatch_permanent_errors=dispatch_permanent_errors,
        )

    async def _process_poll_queue(
        self,
        batch_limit: int | None,
    ) -> _PollCycleStats:
        polled = 0
        poll_transient_errors = 0
        poll_permanent_errors = 0
        processed = 0
        while True:
            if batch_limit is not None and processed >= batch_limit:
                break
            outcome = await self._poll_one_task()
            if outcome is None:
                break
            processed += 1
            match outcome:
                case 'success':
                    polled += 1
                case 'transient':
                    poll_transient_errors += 1
                case 'permanent':
                    poll_permanent_errors += 1
        return _PollCycleStats(
            polled=polled,
            poll_transient_errors=poll_transient_errors,
            poll_permanent_errors=poll_permanent_errors,
        )

    async def _dispatch_one_task(self) -> TaskOutcome | None:
        async with unit_of_work() as uow:
            tasks = await uow.nat_tasks.claim_for_dispatch(1)
            if not tasks:
                return None
            task = tasks[0]
            result = await self._nat_client.send_task(task)
            if isinstance(result, NatWebApiSuccess):
                await uow.nat_tasks.update_after_send(
                    task.id,
                    nat_request_id=result.payload.id,
                    status=result.payload.status,
                )
                await uow.commit()
                logger.info(
                    'Task dispatched: task_id={} nat_request_id={} status={}',
                    task.id,
                    result.payload.id,
                    result.payload.status,
                )
                return 'success'
            if isinstance(result, NatWebApiPermanentError):
                await uow.nat_tasks.mark_send_permanent_failure(
                    task.id,
                    error_message=result.message,
                )
                await uow.commit()
                logger.error(
                    'Task dispatch permanent failure: task_id={} error={}',
                    task.id,
                    result.message,
                )
                return 'permanent'
            logger.warning(
                'Task dispatch transient failure: task_id={} error={}',
                task.id,
                result.message,
            )
            return 'transient'

    async def _poll_one_task(self) -> TaskOutcome | None:
        async with unit_of_work() as uow:
            tasks = await uow.nat_tasks.claim_for_poll(1)
            if not tasks:
                return None
            task = tasks[0]
            if task.nat_request_id is None:
                logger.error(
                    'Poll queue task missing nat_request_id: task_id={}',
                    task.id,
                )
                await uow.nat_tasks.mark_poll_permanent_failure(
                    task.id,
                    error_message='Task is missing nat_request_id for status polling',
                )
                await uow.commit()
                return 'permanent'

            result = await self._nat_client.get_task_status(task.nat_request_id)
            if isinstance(result, NatWebApiSuccess):
                await self._apply_poll_success(uow, task, result.payload)
                await uow.commit()
                logger.info(
                    'Task polled: task_id={} nat_request_id={} status={} progress={}',
                    task.id,
                    task.nat_request_id,
                    result.payload.status,
                    result.payload.progress,
                )
                return 'success'
            if isinstance(result, NatWebApiPermanentError):
                await uow.nat_tasks.mark_poll_permanent_failure(
                    task.id,
                    error_message=result.message,
                )
                await uow.commit()
                logger.error(
                    'Task poll permanent failure: task_id={} error={}',
                    task.id,
                    result.message,
                )
                return 'permanent'
            logger.warning(
                'Task poll transient failure: task_id={} error={}',
                task.id,
                result.message,
            )
            return 'transient'

    async def _apply_poll_success(
        self,
        uow: UnitOfWorkProtocol,
        task: NatTask,
        payload: NatStatusResponse,
    ) -> None:
        await uow.nat_tasks.update_after_poll(
            task.id,
            status=payload.status,
            progress=payload.progress,
            count_of_lines=payload.count_of_lines,
        )
        now = datetime.now(UTC)
        result_files = [
            _to_result_file_entity(task.id, file_item, now=now)
            for file_item in payload.files
        ]
        await uow.nat_task_result_files.replace_for_task(task.id, result_files)


def _to_result_file_entity(
    task_id: UUID,
    file_item: NatWebApiFile,
    *,
    now: datetime,
) -> NatTaskResultFile:
    return NatTaskResultFile(
        id=uuid4(),
        task_id=task_id,
        nat_file_id=file_item.id,
        file_url=file_item.file,
        file_size=file_item.file_size,
        file_type=file_item.type,
        created_at=now,
        updated_at=now,
    )
