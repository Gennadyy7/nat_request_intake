"""User-facing Russian API messages.

Russian copy for API responses lives in MESSAGES only.
Exception: InputColumnName in constants.py matches upload file column headers.
"""

from app.core.config import settings
from app.features.auth.constants import AuthErrorCode
from app.features.nat.constants import (
    ApiErrorCode,
    DeduplicationErrorCode,
    TransformationErrorCode,
    ValidationErrorCode,
)

MESSAGES: dict[str, str] = {
    # ValidationErrorCode
    ValidationErrorCode.MISSING_FILENAME: 'Имя файла не указано',
    ValidationErrorCode.INVALID_FILE_FORMAT: (
        'Неподдерживаемый формат файла. Допустимые форматы: CSV, TXT, XLSX'
    ),
    ValidationErrorCode.EMPTY_FILE: 'Файл не содержит данных',
    ValidationErrorCode.TOO_MANY_ROWS: (
        'Превышено максимально допустимое число строк в файле'
    ),
    ValidationErrorCode.INVALID_HEADERS: ('Заголовки файла не соответствуют ожидаемым'),
    ValidationErrorCode.ROW_COLUMN_COUNT_MISMATCH: (
        'Количество колонок в строке не совпадает с заголовком'  # noqa: RUF001
    ),
    ValidationErrorCode.MISSING_REQUIRED_FIELD: 'Обязательное поле не заполнено',
    ValidationErrorCode.INVALID_DATE_FORMAT: (
        'Некорректный формат даты. Ожидается: дд.мм.гггг'  # noqa: RUF001
    ),
    ValidationErrorCode.INVALID_DATE_RANGE: (
        'Дата окончания не может быть раньше даты начала'
    ),
    ValidationErrorCode.INVALID_IP_FORMAT: 'Некорректный формат IP-адреса',
    ValidationErrorCode.CIDR_NOT_ALLOWED: (
        'CIDR-нотация не допускается. Укажите конкретный IP-адрес'
    ),
    ValidationErrorCode.IP_NOT_BELTELECOM: ('IP-адрес не принадлежит сети Белтелеком'),
    ValidationErrorCode.INVALID_PORT: 'Некорректный номер порта',
    ValidationErrorCode.INVALID_REGION: 'Некорректный код области',
    ValidationErrorCode.NO_VALID_ROWS: ('Файл не содержит ни одной корректной строки'),
    # DeduplicationErrorCode
    DeduplicationErrorCode.DUPLICATE_REQUEST: (
        f'Дубликат: строка с такими данными уже принята. '  # noqa: RUF001
        f'Повторная подача одинаковых строк возможна не ранее чем '
        f'через {settings.NAT_IDEMPOTENCY_WINDOW_MINUTES} мин. после первой.'
    ),
    # TransformationErrorCode
    TransformationErrorCode.EXPANSION_LIMIT_EXCEEDED: (
        'Превышен лимит разворачивания IP-диапазона'
    ),
    # AuthErrorCode
    AuthErrorCode.MISSING_EMAIL: ('Email пользователя не указан в учётной записи'),
    AuthErrorCode.UNAUTHORIZED_SERVICE: (
        'Доступ запрещён: требуется учётная запись сервиса email-poller'
    ),
    AuthErrorCode.INVALID_SENDER_EMAIL: 'Некорректный адрес отправителя',
    # ApiErrorCode
    ApiErrorCode.INTAKE_NOT_FOUND: 'Запрос на загрузку не найден',
    ApiErrorCode.BATCH_NOT_FOUND: 'Пакет не найден',
    ApiErrorCode.BATCH_FILE_NOT_FOUND: 'Исходный файл пакета не найден',
    ApiErrorCode.TASK_NOT_FOUND: 'Задача не найдена',
    ApiErrorCode.INVALID_FILTER_STATUS: 'Недопустимое значение фильтра статуса',
    ApiErrorCode.INVALID_FILTER_TASK_STATUS: (
        'Недопустимое значение фильтра статуса задачи. Допустимо: целое число или null'
    ),
    ApiErrorCode.INVALID_FILTER_NAT_REQUEST_ID: (
        'Недопустимое значение фильтра идентификатора запроса NAT. '
        'Допустимо: целое число или null'
    ),
    ApiErrorCode.INVALID_SORT_BY: 'Недопустимое поле сортировки',
    ApiErrorCode.INVALID_SORT_ORDER: (
        'Недопустимый порядок сортировки. Допустимые значения: asc, desc'
    ),
}


def get_message(code: str) -> str:
    return MESSAGES.get(code, code)
