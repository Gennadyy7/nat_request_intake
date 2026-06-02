from app.features.email.constants import EmailApiErrorCode

MESSAGES: dict[str, str] = {
    EmailApiErrorCode.SENDER_NOT_FOUND: 'Отправитель не найден',
    EmailApiErrorCode.MESSAGE_NOT_FOUND: 'Запись о письме не найдена',
    EmailApiErrorCode.SENDER_ALREADY_EXISTS: (
        'Отправитель с таким email уже есть в белом списке'
    ),
    EmailApiErrorCode.INVALID_FILTER_PROCESSING_STATUS: (
        'Недопустимое значение фильтра статуса обработки письма'
    ),
}


def get_message(code: str) -> str:
    return MESSAGES.get(code, code)
