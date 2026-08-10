from dataclasses import dataclass
from typing import Literal

from nat_batch_notify_worker.app.core.config import settings
from nat_batch_notify_worker.app.core.logging import get_logger
from nat_batch_notify_worker.app.core.unit_of_work import unit_of_work
from nat_batch_notify_worker.app.features.batch_notify.notify_client import (
    BatchNotifyClient,
    BatchNotifySuccess,
)

logger = get_logger(__name__)

NotifyOutcome = Literal['success', 'failure', 'single_stage_paused']


@dataclass(frozen=True, slots=True)
class WorkerCycleStats:
    notified: int = 0
    notify_failures: int = 0
    single_stage_paused: int = 0


@dataclass(frozen=True, slots=True)
class _NotifyCycleStats:
    notified: int = 0
    notify_failures: int = 0
    single_stage_paused: int = 0


class NatBatchNotifyWorkerService:
    def __init__(self, notify_client: BatchNotifyClient) -> None:
        self._notify_client = notify_client

    async def run_once(self) -> WorkerCycleStats:
        logger.info('NAT batch notify worker cycle started')
        batch_limit = self._batch_limit()
        all_failed_paused = await self._pause_single_stage_all_failed(batch_limit)
        notify_stats = await self._process_notify_queue(batch_limit)
        stats = WorkerCycleStats(
            notified=notify_stats.notified,
            notify_failures=notify_stats.notify_failures,
            single_stage_paused=(notify_stats.single_stage_paused + all_failed_paused),
        )
        logger.info(
            'NAT batch notify worker cycle finished: notified={} '
            'notify_failures={} single_stage_paused={}',
            stats.notified,
            stats.notify_failures,
            stats.single_stage_paused,
        )
        return stats

    def _batch_limit(self) -> int | None:
        if settings.NAT_BATCH_NOTIFY_WORKER_PROCESS_ALL:
            return None
        return settings.NAT_BATCH_NOTIFY_WORKER_BATCH_LIMIT

    async def _pause_single_stage_all_failed(self, batch_limit: int | None) -> int:
        paused = 0
        processed = 0
        while True:
            if batch_limit is not None and processed >= batch_limit:
                break
            async with unit_of_work() as uow:
                batches = (
                    await uow.nat_batches.claim_for_single_stage_nat_stop_on_all_failed(
                        1,
                    )
                )
                if not batches:
                    break
                batch = batches[0]
                await uow.nat_batches.set_processing_paused(batch.id, paused=True)
                await uow.commit()
                logger.info(
                    'Single-stage NAT batch paused after all tasks failed: batch_id={}',
                    batch.id,
                )
            paused += 1
            processed += 1
        return paused

    async def _process_notify_queue(
        self,
        batch_limit: int | None,
    ) -> _NotifyCycleStats:
        notified = 0
        notify_failures = 0
        single_stage_paused = 0
        processed = 0
        while True:
            if batch_limit is not None and processed >= batch_limit:
                break
            outcome = await self._notify_one_batch()
            if outcome is None:
                break
            processed += 1
            match outcome:
                case 'success':
                    notified += 1
                case 'failure':
                    notify_failures += 1
                case 'single_stage_paused':
                    single_stage_paused += 1
        return _NotifyCycleStats(
            notified=notified,
            notify_failures=notify_failures,
            single_stage_paused=single_stage_paused,
        )

    async def _notify_one_batch(self) -> NotifyOutcome | None:
        async with unit_of_work() as uow:
            batches = await uow.nat_batches.claim_for_notification(1)
            if not batches:
                return None
            batch = batches[0]
            if batch.single_stage_only:
                await uow.nat_batches.set_processing_paused(batch.id, paused=True)
                await uow.commit()
                logger.info(
                    'Single-stage NAT batch paused before notify: batch_id={}',
                    batch.id,
                )
                return 'single_stage_paused'
            result = await self._notify_client.notify(batch.id)
            if isinstance(result, BatchNotifySuccess):
                await uow.nat_batches.mark_notified(batch.id)
                await uow.commit()
                logger.info('Batch notified: batch_id={}', batch.id)
                return 'success'
            logger.warning(
                'Batch notify failed: batch_id={} error={}',
                batch.id,
                result.message,
            )
            return 'failure'
