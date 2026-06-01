from enum import IntEnum, StrEnum
from typing import Final


class NatTaskStatus(IntEnum):
    CANCELLED = -20
    QUEUED = -1
    LAUNCHED = 10
    IN_PROGRESS = 20
    COMPLETED = 30


class NatIpFieldName(StrEnum):
    INTERNAL_IP = 'internal_ip'
    EXTERNAL_IP = 'external_ip'
    RESOURCE_IP = 'resource_ip'


class InputColumnName(StrEnum):
    DATE_FROM = 'Дата начала'
    DATE_TO = 'Дата окончания'
    INTERNAL_IP = 'Внутренний IP'
    EXTERNAL_IP = 'Внешний IP'
    RESOURCE_IP = 'IP ресурса'
    REGION = 'Область'


class ValidationErrorCode(StrEnum):
    MISSING_FILENAME = 'MISSING_FILENAME'
    INVALID_FILE_FORMAT = 'INVALID_FILE_FORMAT'
    EMPTY_FILE = 'EMPTY_FILE'
    TOO_MANY_ROWS = 'TOO_MANY_ROWS'
    INVALID_HEADERS = 'INVALID_HEADERS'
    ROW_COLUMN_COUNT_MISMATCH = 'ROW_COLUMN_COUNT_MISMATCH'
    MISSING_REQUIRED_FIELD = 'MISSING_REQUIRED_FIELD'
    INVALID_DATE_FORMAT = 'INVALID_DATE_FORMAT'
    INVALID_DATE_RANGE = 'INVALID_DATE_RANGE'
    INVALID_IP_FORMAT = 'INVALID_IP_FORMAT'
    CIDR_NOT_ALLOWED = 'CIDR_NOT_ALLOWED'
    IP_NOT_BELTELECOM = 'IP_NOT_BELTELECOM'
    INVALID_PORT = 'INVALID_PORT'
    INVALID_REGION = 'INVALID_REGION'
    NO_VALID_ROWS = 'NO_VALID_ROWS'


class DeduplicationErrorCode(StrEnum):
    DUPLICATE_REQUEST = 'DUPLICATE_REQUEST'


class TransformationErrorCode(StrEnum):
    EXPANSION_LIMIT_EXCEEDED = 'EXPANSION_LIMIT_EXCEEDED'


type RowErrorCode = (
    ValidationErrorCode | DeduplicationErrorCode | TransformationErrorCode
)


class NatRegionCode(StrEnum):
    BREST = '1'
    VITEBSK = '2'
    GOMEL = '3'
    GRODNO = '4'
    MINSK_REGION = '5'
    MOGILEV = '6'
    MINSK = '7'
    WIFI = '8'


class AllowedFileExtension(StrEnum):
    CSV = '.csv'
    TXT = '.txt'
    XLSX = '.xlsx'


class ApiErrorCode(StrEnum):
    INTAKE_NOT_FOUND = 'INTAKE_NOT_FOUND'
    BATCH_NOT_FOUND = 'BATCH_NOT_FOUND'
    TASK_NOT_FOUND = 'TASK_NOT_FOUND'
    INVALID_FILTER_STATUS = 'INVALID_FILTER_STATUS'
    INVALID_SORT_BY = 'INVALID_SORT_BY'
    INVALID_SORT_ORDER = 'INVALID_SORT_ORDER'


class IntakeStatus(StrEnum):
    REJECTED = 'rejected'
    PARTIALLY_ACCEPTED = 'partially_accepted'
    ACCEPTED = 'accepted'


REQUIRED_COLUMNS: Final[frozenset[InputColumnName]] = frozenset(InputColumnName)

MANDATORY_VALUE_COLUMNS: Final[frozenset[InputColumnName]] = frozenset(
    {
        InputColumnName.DATE_FROM,
        InputColumnName.DATE_TO,
    }
)

COLUMN_TO_IP_FIELD: Final[dict[InputColumnName, NatIpFieldName]] = {
    InputColumnName.INTERNAL_IP: NatIpFieldName.INTERNAL_IP,
    InputColumnName.EXTERNAL_IP: NatIpFieldName.EXTERNAL_IP,
    InputColumnName.RESOURCE_IP: NatIpFieldName.RESOURCE_IP,
}

IP_COLUMNS: Final[frozenset[InputColumnName]] = frozenset(COLUMN_TO_IP_FIELD)
