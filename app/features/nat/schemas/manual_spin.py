from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.features.nat.constants import IntakeSource


class MatchSpinRequest(BaseModel):
    batch_id: UUID


class ManualSpinMatchResponse(BaseModel):
    intake_id: UUID
    intake_number: int = Field(ge=1)
    batch_id: UUID
    result_processing_id: UUID
    source: Literal[IntakeSource.MANUAL_SPIN] = IntakeSource.MANUAL_SPIN
    status: Literal['accepted_for_spin_matching'] = 'accepted_for_spin_matching'
    file_name: str
