from uuid import UUID

from pydantic import BaseModel


class NotifyBatchRequest(BaseModel):
    batch_id: UUID
