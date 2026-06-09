from app.features.nat.constants import IntakeStatus

REPLY_SUBJECT_WHEN_MISSING = 'Результат обработки заявки для SPIN'

INTAKE_STATUS_LABELS: dict[IntakeStatus, str] = {
    IntakeStatus.ACCEPTED: 'Принято',
    IntakeStatus.PARTIALLY_ACCEPTED: 'Частично принято',
    IntakeStatus.REJECTED: 'Отклонено',
}

REJECTED_MESSAGE_FALLBACK = 'Заявка отклонена'
