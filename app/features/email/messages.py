from app.features.email.constants import EmailApiErrorCode, EmailSkipReason

MESSAGES: dict[str, str] = {
    EmailSkipReason.SENDER_NOT_WHITELISTED: ('Отправитель не входит в белый список'),
    EmailSkipReason.NO_ALLOWED_ATTACHMENT: (
        'Нет допустимого вложения (CSV, TXT или XLSX)'
    ),
    EmailSkipReason.PARSE_FAILED: 'Не удалось разобрать письмо',
    EmailSkipReason.NAT_B2B_FAILED: 'Ошибка вызова NAT B2B intake',
    EmailApiErrorCode.SENDER_NOT_FOUND: 'Отправитель не найден',
    EmailApiErrorCode.MESSAGE_NOT_FOUND: 'Запись о письме не найдена',
    EmailApiErrorCode.SENDER_ALREADY_EXISTS: (
        'Отправитель с таким email уже есть в белом списке'
    ),
    EmailApiErrorCode.INVALID_FILTER_PROCESSING_STATUS: (
        'Недопустимое значение фильтра статуса обработки письма'
    ),
    EmailApiErrorCode.INVALID_FILTER_REPLY_STATUS: (
        'Недопустимое значение фильтра статуса ответа на письмо'
    ),
}


def get_message(code: str) -> str:
    return MESSAGES.get(code, code)
