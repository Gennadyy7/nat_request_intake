from enum import StrEnum
from typing import Final


class AssomiTaskStatus(StrEnum):
    PENDING = 'pending'
    COMPLETED = 'completed'
    FAILED = 'failed'


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
