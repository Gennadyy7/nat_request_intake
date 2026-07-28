from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from app.features.assomi.constants import AssomiTaskStatus

ASSOMI_TASK_SORT_COLUMNS: Final[frozenset[str]] = frozenset(
    {'created_at', 'status', 'batch_id', 'completed_at'}
)


@dataclass(frozen=True, slots=True)
class AssomiTaskFilters:
    assomi_id: UUID | None = None
    aggregation_task_id: UUID | None = None
    batch_id: UUID | None = None
    intake_number: int | None = None
    status: AssomiTaskStatus | None = None
    created_at_from: datetime | None = None
    created_at_to: datetime | None = None
    completed_at_from: datetime | None = None
    completed_at_to: datetime | None = None
