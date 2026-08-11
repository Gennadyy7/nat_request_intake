from pathlib import Path
from typing import Literal, Self

from pydantic import EmailStr, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from intake_result_email_worker.app.features.result_email.constants import (
    IntakeResultEmailAttachment,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra='ignore',
        env_file='.env',
        env_file_encoding='utf-8',
    )

    db_url_env: str | None = Field(default=None, validation_alias='DB_URL')

    APP_HOST: str = Field(validation_alias='INTAKE_RESULT_EMAIL_WORKER_APP_HOST')
    APP_PORT: int = Field(validation_alias='INTAKE_RESULT_EMAIL_WORKER_APP_PORT')
    APP_RELOAD: bool = Field(validation_alias='INTAKE_RESULT_EMAIL_WORKER_APP_RELOAD')

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

    INTAKE_RESULT_EMAIL_WORKER_POLL_INTERVAL_SECONDS: int = Field(default=60, ge=1)
    INTAKE_RESULT_EMAIL_WORKER_PROCESS_ALL: bool = True
    INTAKE_RESULT_EMAIL_WORKER_BATCH_LIMIT: int | None = Field(default=None, ge=1)

    INTAKE_RESULT_EMAIL_ENABLED: bool
    INTAKE_RESULT_EMAIL_MAX_ATTACHMENT_BYTES: int = Field(ge=1)
    INTAKE_RESULT_EMAIL_RESPECT_PROCESSING_PAUSE: bool
    INTAKE_RESULT_EMAIL_ATTACHMENT: IntakeResultEmailAttachment

    IMAP_SERVER: str
    IMAP_USER: str
    IMAP_PASSWORD: str
    IMAP_TIMEOUT_SECONDS: float = Field(default=10.0, ge=1.0)

    EMAIL_REPLY_TO: EmailStr
    SMTP_PORT: int = Field(ge=1, le=65535)
    SMTP_USE_SSL: bool
    SMTP_USE_STARTTLS: bool

    ASSOMI_BASE_DIR: str

    @field_validator('ASSOMI_BASE_DIR', mode='before')
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
        if self.INTAKE_RESULT_EMAIL_WORKER_PROCESS_ALL:
            return self
        if self.INTAKE_RESULT_EMAIL_WORKER_BATCH_LIMIT is None:
            raise ValueError(
                'INTAKE_RESULT_EMAIL_WORKER_BATCH_LIMIT is required when '
                'INTAKE_RESULT_EMAIL_WORKER_PROCESS_ALL=false'
            )
        return self

    @model_validator(mode='after')
    def validate_smtp_config(self) -> Self:
        if self.SMTP_USE_SSL is True and self.SMTP_USE_STARTTLS is True:
            raise ValueError(
                'SMTP configuration invalid. SMTP_USE_SSL and SMTP_USE_STARTTLS '
                'cannot both be true.'
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
