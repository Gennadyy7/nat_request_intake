from dataclasses import dataclass
from datetime import datetime

from app.features.nat.constants import NatRegionCode


@dataclass(frozen=True, slots=True)
class ValidatedRow:
    row_index: int
    date_from: datetime
    date_to: datetime
    internal_ip: str | None
    external_ip: str | None
    resource_ip: str | None
    region: NatRegionCode | None

    @property
    def row_number(self) -> int:
        return self.row_index + 1
