from app.features.nat.constants import IntakeSource, IntakeStatus, ValidationErrorCode
from app.features.nat.messages import get_message
from app.features.nat.repository_records import NatIntakeListRecord
from app.features.nat.schemas.intake_list import NatIntakeDetail, NatIntakeListItem


def to_intake_list_item(record: NatIntakeListRecord) -> NatIntakeListItem:
    intake = record.intake
    error_code = _parse_error_code(intake.error_code)
    return NatIntakeListItem(
        id=intake.id,
        number=intake.number,
        sender_email=intake.sender_email,
        file_name=intake.file_name,
        status=IntakeStatus(intake.status),
        source=IntakeSource(intake.source),
        code=error_code,
        message=get_message(error_code) if error_code is not None else None,
        batch_id=record.batch_id,
        processing_paused=record.processing_paused,
        created_at=intake.created_at,
    )


def to_intake_detail(record: NatIntakeListRecord) -> NatIntakeDetail:
    return NatIntakeDetail.model_validate(to_intake_list_item(record).model_dump())


def _parse_error_code(
    value: str | None,
) -> ValidationErrorCode | None:
    if value is None:
        return None
    return ValidationErrorCode(value)
