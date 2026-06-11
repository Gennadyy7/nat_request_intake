from __future__ import annotations

from app.features.nat.constants import NON_TERMINAL_NAT_STATUSES


def is_dispatch_pending(*, status: int | None, error_message: str | None) -> bool:
    return status is None and error_message is None


def is_poll_pending(status: int | None) -> bool:
    return status in NON_TERMINAL_NAT_STATUSES


def is_worker_skipped(*, status: int | None, error_message: str | None) -> bool:
    if status is None:
        return error_message is not None
    return not is_poll_pending(status)
