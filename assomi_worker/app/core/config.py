from functools import cached_property
from pathlib import Path
from typing import Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra='ignore',
        env_file='.env',
        env_file_encoding='utf-8',
    )

    db_url_env: str | None = Field(default=None, validation_alias='DB_URL')

    APP_HOST: str = Field(validation_alias='ASSOMI_WORKER_APP_HOST')
    APP_PORT: int = Field(validation_alias='ASSOMI_WORKER_APP_PORT')
    APP_RELOAD: bool = Field(validation_alias='ASSOMI_WORKER_APP_RELOAD')

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

    ASSOMI_WORKER_POLL_INTERVAL_SECONDS: int = Field(ge=1)
    ASSOMI_WORKER_PROCESS_ALL: bool
    ASSOMI_WORKER_BATCH_LIMIT: int | None = Field(default=None, ge=1)

    ASSOMI_URL: str
    ASSOMI_HTTP_TIMEOUT_SECONDS: int = Field(ge=1)
    ASSOMI_BRANCH: str
    ASSOMI_SYSTEM: str
    ASSOMI_NAME: str
    ASSOMI_IS_TEST: bool
    assomi_systime_timezone_env: str = Field(
        validation_alias='ASSOMI_SYSTIME_TIMEZONE',
    )
    ASSOMI_SYSTIME_FORMAT: str
    ASSOMI_CODE_MSG_MIN: int = Field(ge=1)
    ASSOMI_CODE_MSG_MAX: int = Field(ge=1)
    ASSOMI_CODE_MSG_START: int = Field(ge=1)
    ASSOMI_CODE_MSG_SCOPE: Literal['global', 'header_triple']
    ASSOMI_BASE_DIR: str
    ASSOMI_CSV_ENCODING: Literal['utf-8-sig', 'utf-8', 'cp1251']
    SPIN_AGGREGATED_BASE_DIR: str
    assomi_success_error_codes_env: str = Field(
        validation_alias='ASSOMI_SUCCESS_ERROR_CODES',
    )
    assomi_code_msg_taken_message_markers_env: str = Field(
        validation_alias='ASSOMI_CODE_MSG_TAKEN_MESSAGE_MARKERS',
    )

    @field_validator('assomi_systime_timezone_env', mode='before')
    @classmethod
    def validate_assomi_systime_timezone(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                'ASSOMI_SYSTIME_TIMEZONE must be UTC or a valid IANA timezone name '
                '(e.g. Europe/Minsk).'
            )
        normalized = value.strip()
        try:
            ZoneInfo(normalized)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                'ASSOMI_SYSTIME_TIMEZONE must be UTC or a valid IANA timezone name '
                '(e.g. Europe/Minsk).'
            ) from exc
        return normalized

    @field_validator('ASSOMI_BASE_DIR', 'SPIN_AGGREGATED_BASE_DIR', mode='before')
    @classmethod
    def validate_absolute_base_dir(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError('Base directory path must be a non-empty absolute path')
        normalized = value.strip()
        path = Path(normalized)
        if not path.is_absolute():
            raise ValueError('Base directory path must be an absolute path')
        return normalized

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
        if self.ASSOMI_WORKER_PROCESS_ALL:
            return self
        if self.ASSOMI_WORKER_BATCH_LIMIT is None:
            raise ValueError(
                'ASSOMI_WORKER_BATCH_LIMIT is required when '
                'ASSOMI_WORKER_PROCESS_ALL=false'
            )
        return self

    @model_validator(mode='after')
    def validate_code_msg_range(self) -> Self:
        if self.ASSOMI_CODE_MSG_MIN > self.ASSOMI_CODE_MSG_MAX:
            raise ValueError(
                'ASSOMI_CODE_MSG_MIN must be less than or equal to ASSOMI_CODE_MSG_MAX'
            )
        if not (
            self.ASSOMI_CODE_MSG_MIN
            <= self.ASSOMI_CODE_MSG_START
            <= self.ASSOMI_CODE_MSG_MAX
        ):
            raise ValueError(
                'ASSOMI_CODE_MSG_START must be within '
                '[ASSOMI_CODE_MSG_MIN, ASSOMI_CODE_MSG_MAX]'
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

    @cached_property
    def ASSOMI_SYSTIME_TIMEZONE(self) -> ZoneInfo:  # noqa: N802
        return ZoneInfo(self.assomi_systime_timezone_env)

    @cached_property
    def ASSOMI_SUCCESS_ERROR_CODES(self) -> frozenset[str]:  # noqa: N802
        return frozenset(
            item.strip()
            for item in self.assomi_success_error_codes_env.split(',')
            if item.strip()
        )

    @cached_property
    def ASSOMI_CODE_MSG_TAKEN_MESSAGE_MARKERS(self) -> tuple[str, ...]:  # noqa: N802
        return tuple(
            item.strip()
            for item in self.assomi_code_msg_taken_message_markers_env.split(',')
            if item.strip()
        )


settings = Settings()  # type: ignore[call-arg]
