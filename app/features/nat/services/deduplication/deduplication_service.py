from dataclasses import dataclass

from app.features.nat.constants import DeduplicationErrorCode
from app.features.nat.schemas.validated_row import ValidatedRow


@dataclass(frozen=True, slots=True)
class DeduplicationRowError:
    row_number: int
    error_code: DeduplicationErrorCode


@dataclass(frozen=True, slots=True)
class DeduplicationOutcome:
    accepted_rows: tuple[ValidatedRow, ...]
    errors: tuple[DeduplicationRowError, ...]
