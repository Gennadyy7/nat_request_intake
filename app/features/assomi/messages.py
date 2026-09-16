from app.features.assomi.constants import AssomiApiErrorCode

MESSAGES: dict[str, str] = {
    AssomiApiErrorCode.ASSOMI_TASK_NOT_FOUND: 'Задача обогащения ASSOMI не найдена',
    AssomiApiErrorCode.ASSOMI_NOT_READY: 'Обогащение ASSOMI ещё не завершено',
    AssomiApiErrorCode.ASSOMI_FILE_NOT_FOUND: 'Файл результата ASSOMI не найден',
    AssomiApiErrorCode.INVALID_FILTER_ASSOMI_STATUS: (
        'Недопустимое значение фильтра статуса ASSOMI'
    ),
}


def get_message(code: str) -> str:
    return MESSAGES.get(code, code)
