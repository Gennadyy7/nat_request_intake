from functools import cached_property
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

    APP_HOST: str
    APP_PORT: int
    APP_RELOAD: bool

    KEYCLOAK_URL: str
    KEYCLOAK_REALM: str
    KEYCLOAK_CLIENT_ID: str
    KEYCLOAK_CLIENT_SECRET: str | None

    KEYCLOAK_SWAGGER_CLIENT_ID: str
    KEYCLOAK_SWAGGER_BASE_URL: str

    LOG_LEVEL: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

    admin_roles_env: str = Field(validation_alias='ADMIN_ROLES')

    DB_HOST: str | None = None
    DB_PORT: int | None = None
    DB_NAME: str | None = None
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None

    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 3600
    DB_ECHO: bool = False

    NAT_MAX_BATCH_ROWS: int = Field(ge=1)
    NAT_IDEMPOTENCY_WINDOW_MINUTES: int = Field(ge=1)
    NAT_OUTPUT_DATETIME_FORMAT: str
    NAT_OUTPUT_FIELD_SEPARATOR: str
    NAT_MISSING_FIELD_PLACEHOLDER: str
    NAT_MAX_EXPANSION_PER_FIELD: int = Field(default=256, ge=1)
    NAT_MAX_TOTAL_EXPANSION_PRODUCT: int = Field(default=256, ge=1)
    nat_cidr_allowed_fields_env: str = Field(
        default='internal_ip',
        validation_alias='NAT_CIDR_ALLOWED_FIELDS',
    )
    nat_cidr_expansion_fields_env: str = Field(
        default='internal_ip',
        validation_alias='NAT_CIDR_EXPANSION_FIELDS',
    )
    nat_date_input_formats_env: str = Field(validation_alias='NAT_DATE_INPUT_FORMATS')
    nat_beltelecom_internal_networks_env: str = Field(
        validation_alias='NAT_BELTELECOM_INTERNAL_NETWORKS'
    )

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

    @property
    def DB_URL(self) -> str:  # noqa: N802
        if self.db_url_env:
            return self.db_url_env

        return (
            f'postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}'
            f'@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}'
        )

    @cached_property
    def ADMIN_ROLES(self) -> set[str]:  # noqa: N802
        return {
            role.strip() for role in self.admin_roles_env.split(',') if role.strip()
        }


settings = Settings()  # type: ignore[call-arg]
