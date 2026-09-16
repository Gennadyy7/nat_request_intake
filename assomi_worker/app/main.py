import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException, Response, status
from sqlalchemy import text
import uvicorn

from assomi_worker.app.core.config import settings
from assomi_worker.app.core.database import db_manager, init_db
from assomi_worker.app.core.logging import get_logger, setup_logging
from assomi_worker.app.features.assomi.assomi_client import AssomiClient
from assomi_worker.app.features.assomi.code_msg import CodeMsgSequence
from assomi_worker.app.features.assomi.services.worker import AssomiWorkerService

setup_logging()
logger = get_logger(__name__)


async def _worker_loop(worker_service: AssomiWorkerService) -> None:
    interval = settings.ASSOMI_WORKER_POLL_INTERVAL_SECONDS
    while True:
        try:
            await worker_service.run_once()
        except Exception:
            logger.exception('ASSOMI worker cycle failed')
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info('ASSOMI worker starting up')
    init_db()

    code_msg_sequence = CodeMsgSequence(
        min_value=settings.ASSOMI_CODE_MSG_MIN,
        max_value=settings.ASSOMI_CODE_MSG_MAX,
        start_value=settings.ASSOMI_CODE_MSG_START,
        scope=settings.ASSOMI_CODE_MSG_SCOPE,
    )
    assomi_client = AssomiClient(code_msg_sequence)
    worker_service = AssomiWorkerService(assomi_client)
    worker_task = asyncio.create_task(_worker_loop(worker_service))

    try:
        yield
    finally:
        worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await worker_task
        await assomi_client.aclose()
        await db_manager.close()
        logger.info('ASSOMI worker shutting down')


app = FastAPI(
    lifespan=lifespan,
    title='ASSOMI Worker',
    description='Background worker for ASSOMI enrichment of completed SPIN matching tasks',
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
    logger.info(
        'Starting ASSOMI worker on {}:{}',
        settings.APP_HOST,
        settings.APP_PORT,
    )
    uvicorn.run(
        'assomi_worker.app.main:app',
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == '__main__':
    main()
