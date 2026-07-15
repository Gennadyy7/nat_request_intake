from enum import IntEnum, StrEnum
from typing import Final


class NatTaskStatus(IntEnum):
    LOCAL_ABANDONED = -999
    CANCELLED = -20
    QUEUED = -1
    LAUNCHED = 10
    IN_PROGRESS = 20
    COMPLETED = 30


NON_TERMINAL_NAT_STATUSES: Final[frozenset[int]] = frozenset(
    {
        NatTaskStatus.QUEUED,
        NatTaskStatus.LAUNCHED,
        NatTaskStatus.IN_PROGRESS,
    }
)


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
    DATE_RANGE_LIMIT_EXCEEDED = 'DATE_RANGE_LIMIT_EXCEEDED'
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


MEDIA_TYPE_BY_EXTENSION: Final[dict[AllowedFileExtension, str]] = {
    AllowedFileExtension.CSV: 'text/csv; charset=utf-8',
    AllowedFileExtension.TXT: 'text/plain; charset=utf-8',
    AllowedFileExtension.XLSX: (
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    ),
}


TASK_FILTER_NULL_SENTINEL: Final[str] = 'null'


class NatResultProcessingStatus(StrEnum):
    PENDING = 'pending'
    DOWNLOADING = 'downloading'
    AGGREGATING = 'aggregating'
    MATCHING_SPIN = 'matching_spin'
    COMPLETED = 'completed'
    FAILED = 'failed'


class ResultProcessingGetStatus(StrEnum):
    OK = 'ok'
    BATCH_NOT_FOUND = 'batch_not_found'
    RESULT_PROCESSING_NOT_FOUND = 'result_processing_not_found'


class ApiErrorCode(StrEnum):
    INTAKE_NOT_FOUND = 'INTAKE_NOT_FOUND'
    BATCH_NOT_FOUND = 'BATCH_NOT_FOUND'
    BATCH_FILE_NOT_FOUND = 'BATCH_FILE_NOT_FOUND'
    TASK_NOT_FOUND = 'TASK_NOT_FOUND'
    RESULT_PROCESSING_NOT_FOUND = 'RESULT_PROCESSING_NOT_FOUND'
    INVALID_FILTER_STATUS = 'INVALID_FILTER_STATUS'
    INVALID_FILTER_TASK_STATUS = 'INVALID_FILTER_TASK_STATUS'
    INVALID_FILTER_NAT_REQUEST_ID = 'INVALID_FILTER_NAT_REQUEST_ID'
    INVALID_FILTER_RESULT_PROCESSING_STATUS = 'INVALID_FILTER_RESULT_PROCESSING_STATUS'
    INVALID_SORT_BY = 'INVALID_SORT_BY'
    INVALID_SORT_ORDER = 'INVALID_SORT_ORDER'
    INTAKE_NOT_PAUSABLE = 'INTAKE_NOT_PAUSABLE'
    BATCH_ALREADY_NOTIFIED = 'BATCH_ALREADY_NOTIFIED'


class IntakeStatus(StrEnum):
    REJECTED = 'rejected'
    PARTIALLY_ACCEPTED = 'partially_accepted'
    ACCEPTED = 'accepted'


def is_file_level_intake_rejection(error_code: str | None) -> bool:
    if error_code is None:
        return False
    return error_code != ValidationErrorCode.NO_VALID_ROWS.value


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
