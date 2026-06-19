from dataclasses import dataclass
from uuid import UUID

from app.features.nat.models import NatBatch, NatIntake


@dataclass(frozen=True, slots=True)
class NatBatchListRecord:
    batch: NatBatch
    sender_email: str
    original_file_name: str
    tasks_count: int


@dataclass(frozen=True, slots=True)
class NatBatchDetailRecord:
    batch: NatBatch
    sender_email: str
    original_file_name: str
    tasks_count: int


@dataclass(frozen=True, slots=True)
class NatIntakeListRecord:
    intake: NatIntake
    batch_id: UUID | None
    processing_paused: bool | None
