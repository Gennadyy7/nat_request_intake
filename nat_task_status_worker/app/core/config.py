from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra='ignore',
        env_file='.env',
        env_file_encoding='utf-8',
    )

    db_url_env: str | None = Field(default=None, validation_alias='DB_URL')

    APP_HOST: str = Field(validation_alias='NAT_TASK_STATUS_WORKER_APP_HOST')
    APP_PORT: int = Field(validation_alias='NAT_TASK_STATUS_WORKER_APP_PORT')
    APP_RELOAD: bool = Field(validation_alias='NAT_TASK_STATUS_WORKER_APP_RELOAD')

    LOG_LEVEL: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

    DB_HOST: str | None = None
    DB_PORT: int | None = None
    DB_NAME: str | None = None
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None

    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 3600
    DB_ECHO: bool = False

    NAT_TASK_STATUS_WORKER_POLL_INTERVAL_SECONDS: int = Field(ge=1)
    NAT_TASK_STATUS_WORKER_PROCESS_ALL_NON_TERMINAL: bool
    NAT_TASK_STATUS_WORKER_BATCH_LIMIT: int | None = Field(default=None, ge=1)

    NAT_WEBAPI_URL: str
    NAT_USER: str
    NAT_PASSWORD: str
    NAT_WEBAPI_DATETIME_FORMAT: str
    NAT_WEBAPI_HTTP_TIMEOUT_SECONDS: int = Field(ge=1)

    NAT_MISSING_FIELD_PLACEHOLDER: str

    @model_validator(mode='after')
    def validate_db_config(self) -> Self:
        if self.db_url_env:
            return self

        missing = [
            name
            for name, value in {
                'DB_HOST': self.DB_HOST,
                'DB_PORT': self.DB_PORT,
                'DB_NAME': self.DB_NAME,
                'DB_USER': self.DB_USER,
                'DB_PASSWORD': self.DB_PASSWORD,
            }.items()
            if not value
        ]

        if missing:
            raise ValueError(
                f'Database configuration incomplete. DB_URL is not set. '
                f'Required environment variables: {", ".join(missing)}'
            )

        return self

    @model_validator(mode='after')
    def validate_batch_limit(self) -> Self:
        if self.NAT_TASK_STATUS_WORKER_PROCESS_ALL_NON_TERMINAL:
            return self
        if self.NAT_TASK_STATUS_WORKER_BATCH_LIMIT is None:
            raise ValueError(
                'NAT_TASK_STATUS_WORKER_BATCH_LIMIT is required when '
                'NAT_TASK_STATUS_WORKER_PROCESS_ALL_NON_TERMINAL=false'
            )
        return self

    @property
    def DB_URL(self) -> str:  # noqa: N802
        if self.db_url_env:
            return self.db_url_env

        return (
            f'postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}'
            f'@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}'
        )


settings = Settings()  # type: ignore[call-arg]
