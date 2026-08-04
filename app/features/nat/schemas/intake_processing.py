from pydantic import BaseModel, Field


class IntakeProcessingUpdate(BaseModel):
    paused: bool = Field(
        description=(
            'When true, NAT dispatch, batch notify, and ASSOMI enqueue/claim '
            'skip the batch; NAT poll continues for already sent tasks. '
            'Final result email respects pause only when configured in the '
            'result-email worker.'
        ),
    )


class GlobalProcessingUpdate(BaseModel):
    paused: bool = Field(
        description=(
            'When true, NAT dispatch, batch notify, and ASSOMI enqueue/claim '
            'skip all batches; NAT poll continues for already sent tasks. '
            'Final result email respects pause only when configured in the '
            'result-email worker. Per-batch processing_paused is unchanged.'
        ),
    )


class GlobalProcessingState(BaseModel):
    paused: bool = Field(
        description=(
            'When true, NAT dispatch, batch notify, and ASSOMI enqueue/claim '
            'skip all batches; NAT poll continues for already sent tasks. '
            'Final result email respects pause only when configured in the '
            'result-email worker. Per-batch processing_paused is unchanged.'
        ),
    )
