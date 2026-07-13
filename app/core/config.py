from functools import cached_property
from typing import Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.features.nat.constants import NatIpFieldName


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra='ignore',
        env_file='.env',
        env_file_encoding='utf-8',
    )

    db_url_env: str | None = Field(default=None, validation_alias='DB_URL')

    APP_ROOT_PATH: str = ''

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

    EMAIL_POLLER_CLIENT_ID: str = 'email_poller_client'

    DB_HOST: str | None = None
    DB_PORT: int | None = None
    DB_NAME: str | None = None
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None

    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 3600
    DB_ECHO: bool = False

    API_PAGINATION_DEFAULT_LIMIT: int = Field(ge=1)
    API_PAGINATION_MAX_LIMIT: int = Field(ge=1)

    NAT_MAX_BATCH_ROWS: int = Field(ge=1)
    NAT_IDEMPOTENCY_WINDOW_MINUTES: int = Field(ge=1)
    NAT_TASK_DISPLAY_DATETIME_FORMAT: str
    NAT_INPUT_FIELD_SEPARATOR: str
    NAT_MISSING_FIELD_PLACEHOLDER: str
    NAT_UPLOAD_BASE_DIR: str = 'backend/uploads/nat'
    nat_upload_date_timezone_env: str = Field(
        validation_alias='NAT_UPLOAD_DATE_TIMEZONE',
    )
    NAT_MAX_EXPANSION_PER_FIELD: int = Field(default=256, ge=1)
    NAT_MAX_TOTAL_EXPANSION_PRODUCT: int = Field(default=256, ge=1)
    nat_cidr_allowed_fields_env: str = Field(
        validation_alias='NAT_CIDR_ALLOWED_FIELDS',
    )
    nat_cidr_expansion_fields_env: str = Field(
        validation_alias='NAT_CIDR_EXPANSION_FIELDS',
    )
    nat_date_input_formats_env: str = Field(validation_alias='NAT_DATE_INPUT_FORMATS')
    nat_beltelecom_internal_networks_env: str = Field(
        validation_alias='NAT_BELTELECOM_INTERNAL_NETWORKS'
    )

    @field_validator(
        'nat_cidr_allowed_fields_env',
        'nat_cidr_expansion_fields_env',
        mode='before',
    )
    @classmethod
    def validate_nat_ip_field_names(cls, value: str) -> str:
        for item in value.split(','):
            stripped = item.strip()
            if not stripped:
                continue
            try:
                NatIpFieldName(stripped)
            except ValueError as exc:
                raise ValueError(
                    f'Invalid NAT IP field name {stripped!r}. '
                    f'Allowed values: {", ".join(member.value for member in NatIpFieldName)}'
                ) from exc
        return value

    @field_validator('nat_upload_date_timezone_env', mode='before')
    @classmethod
    def validate_nat_upload_date_timezone(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError('NAT_UPLOAD_DATE_TIMEZONE must be a string')
        if not value:
            raise ValueError('NAT_UPLOAD_DATE_TIMEZONE must not be empty')
        if value != value.strip():
            raise ValueError(
                'NAT_UPLOAD_DATE_TIMEZONE must not contain leading or trailing whitespace'
            )
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                f'Invalid NAT_UPLOAD_DATE_TIMEZONE value {value!r}. '
                'Use UTC or a valid IANA timezone name (e.g. Europe/Minsk).'
            ) from exc
        return value

    @field_validator('APP_ROOT_PATH', mode='before')
    @classmethod
    def validate_app_root_path(cls, value: object) -> str:
        if value is None:
            return ''
        if not isinstance(value, str):
            raise ValueError('APP_ROOT_PATH must be a string')
        if value == '':
            return ''
        if any(character.isspace() for character in value):
            raise ValueError('APP_ROOT_PATH must not contain whitespace')
        if not value.startswith('/'):
            raise ValueError('APP_ROOT_PATH must be empty or start with "/"')
        if value.endswith('/'):
            raise ValueError('APP_ROOT_PATH must not end with "/"')
        if '//' in value:
            raise ValueError('APP_ROOT_PATH must not contain "//"')
        return value

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
    def validate_pagination_limits(self) -> Self:
        if self.API_PAGINATION_MAX_LIMIT < self.API_PAGINATION_DEFAULT_LIMIT:
            raise ValueError(
                'API_PAGINATION_MAX_LIMIT must be greater than or equal to '
                'API_PAGINATION_DEFAULT_LIMIT'
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

    @cached_property
    def NAT_CIDR_ALLOWED_FIELDS(self) -> frozenset[NatIpFieldName]:  # noqa: N802
        return frozenset(
            NatIpFieldName(item.strip())
            for item in self.nat_cidr_allowed_fields_env.split(',')
            if item.strip()
        )

    @cached_property
    def NAT_CIDR_EXPANSION_FIELDS(self) -> frozenset[NatIpFieldName]:  # noqa: N802
        return frozenset(
            NatIpFieldName(item.strip())
            for item in self.nat_cidr_expansion_fields_env.split(',')
            if item.strip()
        )

    @cached_property
    def NAT_DATE_INPUT_FORMATS(self) -> set[str]:  # noqa: N802
        return {
            date_input_format.strip()
            for date_input_format in self.nat_date_input_formats_env.split(',')
            if date_input_format.strip()
        }

    @cached_property
    def NAT_BELTELECOM_INTERNAL_NETWORKS(self) -> set[str]:  # noqa: N802
        return {
            internal_network.strip()
            for internal_network in self.nat_beltelecom_internal_networks_env.split(',')
            if internal_network.strip()
        }

    @cached_property
    def NAT_UPLOAD_DATE_TIMEZONE(self) -> ZoneInfo:  # noqa: N802
        return ZoneInfo(self.nat_upload_date_timezone_env)


settings = Settings()  # type: ignore[call-arg]
