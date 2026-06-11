from __future__ import annotations

from datetime import datetime
from typing import Protocol

from nat_task_status_worker.app.features.task_status.utils.datetime_formatting import (
    format_task_datetime_for_webapi_value,
)
from nat_task_status_worker.app.features.task_status.utils.region_formatting import (
    format_region_for_nat_value,
)


class WorkerSettings(Protocol):
    NAT_USER: str
    NAT_PASSWORD: str
    NAT_WEBAPI_DATETIME_FORMAT: str
    NAT_MISSING_FIELD_PLACEHOLDER: str


class NatTaskSendPayload(Protocol):
    datetime_from: datetime
    datetime_to: datetime
    src_xlated: str
    src_port_xlated: int | None
    src: str
    src_port: int | None
    dst: str
    dst_port: int | None
    region: str


def build_send_form_data(
    task: NatTaskSendPayload,
    *,
    worker_settings: WorkerSettings,
) -> dict[str, str]:
    data: dict[str, str] = {
        'ACTION': 'send',
        'user': worker_settings.NAT_USER,
        'psw': worker_settings.NAT_PASSWORD,
        'datetime_from': format_task_datetime_for_webapi_value(
            task.datetime_from,
            fmt=worker_settings.NAT_WEBAPI_DATETIME_FORMAT,
        ),
        'datetime_to': format_task_datetime_for_webapi_value(
            task.datetime_to,
            fmt=worker_settings.NAT_WEBAPI_DATETIME_FORMAT,
        ),
        'srcXlated': task.src_xlated,
        'src': task.src,
        'dst': task.dst,
        'region': format_region_for_nat_value(
            task.region,
            missing_placeholder=worker_settings.NAT_MISSING_FIELD_PLACEHOLDER,
        ),
    }
    if task.src_port_xlated is not None:
        data['srcPortXlated'] = str(task.src_port_xlated)
    if task.src_port is not None:
        data['srcPort'] = str(task.src_port)
    if task.dst_port is not None:
        data['dstPort'] = str(task.dst_port)
    return data
