from pydantic import BaseModel, Field


class IntakeProcessingUpdate(BaseModel):
    paused: bool = Field(
        description=(
            'When true, dispatch and notify workers skip the batch; '
            'poll continues for already sent tasks'
        ),
    )
