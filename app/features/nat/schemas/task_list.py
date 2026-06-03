from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NatTaskListItem(BaseModel):
    id: UUID
    batch_id: UUID
    nat_request_id: int | None = None
    datetime_from: str
    datetime_to: str
    src_xlated: str
    src_port_xlated: int | None = None
    src: str
    src_port: int | None = None
    dst: str
    dst_port: int | None = None
    region: str
    status: int | None = None
    progress: int | None = None
    nat_response_file: str | None = None
    count_of_lines: str | None = None
    file_size: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class NatTaskDetail(BaseModel):
    id: UUID
    batch_id: UUID
    nat_request_id: int | None = None
    datetime_from: str
    datetime_to: str
    src_xlated: str
    src_port_xlated: int | None = None
    src: str
    src_port: int | None = None
    dst: str
    dst_port: int | None = None
    region: str
    status: int | None = None
    progress: int | None = None
    nat_response_file: str | None = None
    count_of_lines: str | None = None
    file_size: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
