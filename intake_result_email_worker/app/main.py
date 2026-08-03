import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException, Response, status
from sqlalchemy import text
import uvicorn

from intake_result_email_worker.app.core.config import settings
from intake_result_email_worker.app.core.database import db_manager, init_db
from intake_result_email_worker.app.core.logging import get_logger, setup_logging
from intake_result_email_worker.app.features.result_email.services.worker import (
    IntakeResultEmailWorkerService,
)

setup_logging()
logger = get_logger(__name__)


async def _worker_loop(worker_service: IntakeResultEmailWorkerService) -> None:
    interval = settings.INTAKE_RESULT_EMAIL_WORKER_POLL_INTERVAL_SECONDS
    while True:
        try:
            await worker_service.run_once()
        except Exception:
            logger.exception('Intake result email worker cycle failed')
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info('Intake result email worker starting up')
    init_db()

    worker_service = IntakeResultEmailWorkerService()
    worker_task = asyncio.create_task(_worker_loop(worker_service))

    try:
        yield
    finally:
        worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await worker_task
        await db_manager.close()
        logger.info('Intake result email worker shutting down')


app = FastAPI(
    lifespan=lifespan,
    title='Intake Result Email Worker',
    description=(
        'Background worker for sending final NAT/SPIN/ASSOMI result emails '
        'to intake senders'
    ),
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
        'Starting intake result email worker on {}:{}',
        settings.APP_HOST,
        settings.APP_PORT,
    )
    uvicorn.run(
        'intake_result_email_worker.app.main:app',
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == '__main__':
    main()
