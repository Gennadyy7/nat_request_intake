from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi_keycloak_middleware import setup_keycloak_middleware
from sqlalchemy import text
import uvicorn

from app.api import api_router
from app.core.config import settings
from app.core.csp import (
    CSP_API_POLICY,
    ContentSecurityPolicyMiddleware,
    build_docs_csp_policy,
    collect_keycloak_origins,
)
from app.core.database import db_manager
from app.core.keycloak import get_keycloak_config, map_user
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info('Application starting up')
    db_manager.init()
    try:
        yield
    finally:
        await db_manager.close()
        logger.info('Application shutting down')


_docs_url = '/docs' if settings.DOCS_ENABLED else None
_redoc_url = '/redoc' if settings.DOCS_ENABLED else None
_openapi_url = '/openapi.json' if settings.DOCS_ENABLED else None

app = FastAPI(
    lifespan=lifespan,
    title='Nat Request Intake',
    description='',
    version='0.1.0',
    root_path=settings.APP_ROOT_PATH,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

setup_keycloak_middleware(
    app,
    keycloak_configuration=get_keycloak_config(),
    user_mapper=map_user,
    exclude_patterns=[
        '^/$',
        '/health',
        '/docs',
        '/openapi.json',
        '/api/auth/public',
        # '/api/v1/',
    ],
    add_swagger_auth=True,
    swagger_openId_base_url=settings.KEYCLOAK_SWAGGER_BASE_URL,
)

app.add_middleware(
    middleware_class=CORSMiddleware,  # type: ignore
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

_keycloak_origins = collect_keycloak_origins(
    settings.KEYCLOAK_SWAGGER_BASE_URL,
    settings.KEYCLOAK_URL,
)
app.add_middleware(
    ContentSecurityPolicyMiddleware,
    enabled=settings.CSP_ENABLED,
    docs_enabled=settings.DOCS_ENABLED,
    api_policy=CSP_API_POLICY,
    docs_policy=build_docs_csp_policy(_keycloak_origins),
)

_api_prefix = '' if settings.APP_ROOT_PATH else '/api'
app.include_router(api_router, prefix=_api_prefix)


@app.get('/')
async def root() -> Response:
    if not settings.DOCS_ENABLED:
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    docs_path = f'{settings.APP_ROOT_PATH}/docs' if settings.APP_ROOT_PATH else '/docs'
    return Response(status_code=status.HTTP_302_FOUND, headers={'Location': docs_path})


@app.get('/health')
async def health_check() -> dict[str, str]:
    logger.debug('Health check requested')
    try:
        async with db_manager.get_session() as session:
            await session.execute(text('SELECT 1'))
    except Exception as e:
        logger.error(f'Health check failed: {e}')
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Service unavailable',
        ) from e
    return {'status': 'ok'}


def main() -> None:
    setup_logging()
    logger.info(f'Starting server on {settings.APP_HOST}:{settings.APP_PORT}')
    uvicorn.run(
        'app.main:app',
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == '__main__':
    main()
