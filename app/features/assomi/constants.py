from enum import StrEnum
from typing import Final


class AssomiTaskStatus(StrEnum):
    PENDING = 'pending'
    COMPLETED = 'completed'
    FAILED = 'failed'


class AssomiApiErrorCode(StrEnum):
    ASSOMI_TASK_NOT_FOUND = 'ASSOMI_TASK_NOT_FOUND'
    ASSOMI_NOT_READY = 'ASSOMI_NOT_READY'
    ASSOMI_FILE_NOT_FOUND = 'ASSOMI_FILE_NOT_FOUND'
    INVALID_FILTER_ASSOMI_STATUS = 'INVALID_FILTER_ASSOMI_STATUS'


ASSOMI_CSV_HEADERS: Final[tuple[str, str, str, str, str]] = (
    'Договор',
    'Логин',
    'ФИО',
    'Адрес предоставления услуги',
    'Адрес регистрации',
)

ASSOMI_MISSING_FIELD_PLACEHOLDER: Final[str] = '-'

ASSOMI_CSV_DELIMITER: Final[str] = ';'

ASSOMI_CODE_MSG_TAKEN_MESSAGE_MARKERS: Final[tuple[str, ...]] = (
    'уже находится в базе',
    'таким номером',
)

SPIN_MATCHED_PATH_SUFFIX: Final[str] = '_spin_matched.csv'
ASSOMI_OUTPUT_SUFFIX: Final[str] = '_assomi.csv'
