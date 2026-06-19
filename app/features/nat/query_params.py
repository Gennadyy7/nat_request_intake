from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from app.features.nat.constants import IntakeStatus

SortOrder = Literal['asc', 'desc']

NAT_INTAKE_SORT_COLUMNS: Final[frozenset[str]] = frozenset(
    {'created_at', 'file_name', 'sender_email'}
)
NAT_BATCH_SORT_COLUMNS: Final[frozenset[str]] = frozenset(
    {'created_at', 'file_name', 'sender_email', 'row_count'}
)
NAT_TASK_SORT_COLUMNS: Final[frozenset[str]] = frozenset(
    {'created_at', 'status', 'batch_id'}
)


@dataclass(frozen=True, slots=True)
class SortParams:
    sort_by: str
    sort_order: SortOrder


@dataclass(frozen=True, slots=True)
class NatIntakeFilters:
    intake_id: UUID | None = None
    sender_email: str | None = None
    file_name: str | None = None
    created_at_from: datetime | None = None
    created_at_to: datetime | None = None
    status: IntakeStatus | None = None
    processing_paused: bool | None = None


@dataclass(frozen=True, slots=True)
class NatBatchFilters:
    batch_id: UUID | None = None
    sender_email: str | None = None
    file_name: str | None = None
    created_at_from: datetime | None = None
    created_at_to: datetime | None = None
    row_count_min: int | None = None
    row_count_max: int | None = None


@dataclass(frozen=True, slots=True)
class NatTaskFilters:
    batch_id: UUID | None = None
    status: int | None = None
    status_is_null: bool = False
    nat_request_id: int | None = None
    nat_request_id_is_null: bool = False
    region: str | None = None
    created_at_from: datetime | None = None
    created_at_to: datetime | None = None
