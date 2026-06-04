import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException, Response, status
from sqlalchemy import text
import uvicorn

from email_poller.app.core.config import settings
from email_poller.app.core.database import db_manager, init_db
from email_poller.app.core.keycloak_token import KeycloakTokenProvider
from email_poller.app.core.logging import get_logger, setup_logging
from email_poller.app.core.nat_client import NatIntakeClient
from email_poller.app.features.email_monitor.services.poller import EmailPollService

logger = get_logger(__name__)


async def _poll_loop(poll_service: EmailPollService) -> None:
    interval = settings.EMAIL_POLL_INTERVAL_SECONDS
    while True:
        try:
            await poll_service.poll_once()
        except Exception:
            logger.exception('Email poll cycle failed')
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info('Email poller starting up')
    init_db()

    token_provider = KeycloakTokenProvider()
    nat_client = NatIntakeClient(token_provider)
    poll_service = EmailPollService(nat_client)
    poll_task = asyncio.create_task(_poll_loop(poll_service))

    try:
        yield
    finally:
        poll_task.cancel()
        with suppress(asyncio.CancelledError):
            await poll_task
        await nat_client.aclose()
        await token_provider.aclose()
        await db_manager.close()
        logger.info('Email poller shutting down')


app = FastAPI(
    lifespan=lifespan,
    title='Email Poller',
    description='IMAP polling worker',
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
    logger.info('Starting email poller on {}:{}', settings.APP_HOST, settings.APP_PORT)
    uvicorn.run(
        'email_poller.app.main:app',
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == '__main__':
    main()
