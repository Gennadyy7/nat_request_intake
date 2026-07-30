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

_SECONDS_PER_DAY = 86_400
_SECONDS_PER_HOUR = 3_600
_SECONDS_PER_MINUTE = 60


def format_duration_seconds_ru(total_seconds: int) -> str:
    if total_seconds < 0:
        raise ValueError('total_seconds must be non-negative')

    days, remainder = divmod(total_seconds, _SECONDS_PER_DAY)
    hours, remainder = divmod(remainder, _SECONDS_PER_HOUR)
    minutes, seconds = divmod(remainder, _SECONDS_PER_MINUTE)

    parts: list[str] = []
    if days:
        parts.append(f'{days} {_ru_plural(days, "день", "дня", "дней")}')
    if hours:
        parts.append(f'{hours} {_ru_plural(hours, "час", "часа", "часов")}')
    if minutes:
        parts.append(f'{minutes} {_ru_plural(minutes, "минута", "минуты", "минут")}')
    if seconds or not parts:
        parts.append(f'{seconds} {_ru_plural(seconds, "секунда", "секунды", "секунд")}')
    return ' '.join(parts)


def _ru_plural(value: int, one: str, few: str, many: str) -> str:
    mod100 = abs(value) % 100
    mod10 = mod100 % 10
    if 11 <= mod100 <= 14:
        return many
    if mod10 == 1:
        return one
    if 2 <= mod10 <= 4:
        return few
    return many


MESSAGES: dict[str, str] = {
    # ValidationErrorCode
    ValidationErrorCode.MISSING_FILENAME: 'Имя файла не указано',
    ValidationErrorCode.INVALID_FILE_FORMAT: (
        'Неподдерживаемый формат файла. Допустимые форматы: CSV, TXT, XLSX'
    ),
    ValidationErrorCode.MANUAL_SPIN_CSV_REQUIRED: (
        'Неподдерживаемый формат файла. Для ручного сопоставления SPIN допустим CSV'
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
    ValidationErrorCode.DATE_RANGE_NOT_IN_PAST: (
        'Дата окончания должна быть раньше текущей даты'
    ),
    ValidationErrorCode.DATE_RANGE_LIMIT_EXCEEDED: (
        'Превышена максимально допустимая длительность интервала между датой '
        'начала и датой окончания '
        f'(не более {format_duration_seconds_ru(settings.NAT_MAX_DATE_RANGE_SECONDS)})'
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
    AuthErrorCode.INSUFFICIENT_PERMISSIONS: (
        'Недостаточно прав для управления белым списком отправителей'
    ),
    # ApiErrorCode
    ApiErrorCode.INTAKE_NOT_FOUND: 'Запрос на загрузку не найден',
    ApiErrorCode.BATCH_NOT_FOUND: 'Пакет не найден',
    ApiErrorCode.BATCH_FILE_NOT_FOUND: 'Исходный файл пакета не найден',
    ApiErrorCode.TASK_NOT_FOUND: 'Задача не найдена',
    ApiErrorCode.RESULT_PROCESSING_NOT_FOUND: (
        'Задача пост-обработки пакета не найдена'
    ),
    ApiErrorCode.RESULT_PROCESSING_NOT_READY: (
        'Пост-обработка пакета ещё не завершена'
    ),
    ApiErrorCode.RESULT_PROCESSING_FILE_NOT_FOUND: (
        'Файл результата пост-обработки не найден'
    ),
    ApiErrorCode.INVALID_FILTER_STATUS: 'Недопустимое значение фильтра статуса',
    ApiErrorCode.INVALID_FILTER_SOURCE: 'Недопустимое значение фильтра источника',
    ApiErrorCode.INVALID_FILTER_TASK_STATUS: (
        'Недопустимое значение фильтра статуса задачи. Допустимо: целое число или null'
    ),
    ApiErrorCode.INVALID_FILTER_NAT_REQUEST_ID: (
        'Недопустимое значение фильтра идентификатора запроса NAT. '
        'Допустимо: целое число или null'
    ),
    ApiErrorCode.INVALID_FILTER_RESULT_PROCESSING_STATUS: (
        'Недопустимое значение фильтра статуса пост-обработки'
    ),
    ApiErrorCode.INVALID_SORT_BY: 'Недопустимое поле сортировки',
    ApiErrorCode.INVALID_SORT_ORDER: (
        'Недопустимый порядок сортировки. Допустимые значения: asc, desc'
    ),
    ApiErrorCode.INTAKE_NOT_PAUSABLE: (
        'Заявку нельзя приостановить: отсутствует принятый пакет обработки'
    ),
    ApiErrorCode.BATCH_ALREADY_NOTIFIED: ('Обработка уже передана внешнему сервису'),
    ApiErrorCode.MANUAL_SPIN_MATCH_FAILED: (
        'Сервис SPIN отклонил запуск ручного сопоставления'
    ),
    ApiErrorCode.MANUAL_SPIN_MATCH_UNAVAILABLE: ('Сервис SPIN временно недоступен'),
}


def get_message(code: str) -> str:
    return MESSAGES.get(code, code)
