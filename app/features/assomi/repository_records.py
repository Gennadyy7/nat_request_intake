from dataclasses import dataclass

from app.features.assomi.models import AssomiTask


@dataclass(frozen=True, slots=True)
class AssomiTaskListRecord:
    task: AssomiTask
    intake_number: int
