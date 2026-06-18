import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException, Response, status
from sqlalchemy import text
import uvicorn

from nat_batch_notify_worker.app.core.config import settings
from nat_batch_notify_worker.app.core.database import db_manager, init_db
from nat_batch_notify_worker.app.core.keycloak_token import KeycloakTokenProvider
from nat_batch_notify_worker.app.core.logging import get_logger, setup_logging
from nat_batch_notify_worker.app.features.batch_notify.notify_client import (
    BatchNotifyClient,
)
from nat_batch_notify_worker.app.features.batch_notify.services.worker import (
    NatBatchNotifyWorkerService,
)

logger = get_logger(__name__)


async def _worker_loop(worker_service: NatBatchNotifyWorkerService) -> None:
    interval = settings.NAT_BATCH_NOTIFY_WORKER_POLL_INTERVAL_SECONDS
    while True:
        try:
            await worker_service.run_once()
        except Exception:
            logger.exception('NAT batch notify worker cycle failed')
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info('NAT batch notify worker starting up')
    init_db()

    token_provider = KeycloakTokenProvider()
    notify_client = BatchNotifyClient(token_provider)
    worker_service = NatBatchNotifyWorkerService(notify_client)
    worker_task = asyncio.create_task(_worker_loop(worker_service))

    try:
        yield
    finally:
        worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await worker_task
        await notify_client.aclose()
        await token_provider.aclose()
        await db_manager.close()
        logger.info('NAT batch notify worker shutting down')


app = FastAPI(
    lifespan=lifespan,
    title='NAT Batch Notify Worker',
    description='Background worker for notifying external services about ready NAT batches',
    version='0.1.0',
)


@app.get('/')
async def root_redirect() -> Response:
    return Response(status_code=status.HTTP_404_NOT_FOUND)


@app.get('/health')
async def health_check() -> dict[str, str]:
    logger.debug('Health check requested')
    try:
        async with db_manager.get_session() as session:
            await session.execute(text('SELECT 1'))
    except Exception as exc:
        logger.error('Health check failed: {}', exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Service unavailable',
        ) from exc
    return {'status': 'ok'}


def main() -> None:
    setup_logging()
    logger.info(
        'Starting NAT batch notify worker on {}:{}',
        settings.APP_HOST,
        settings.APP_PORT,
    )
    uvicorn.run(
        'nat_batch_notify_worker.app.main:app',
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == '__main__':
    main()
