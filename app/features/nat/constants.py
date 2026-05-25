from enum import IntEnum


class NatTaskStatus(IntEnum):
    CANCELLED = -20
    QUEUED = -1
    LAUNCHED = 10
    IN_PROGRESS = 20
    COMPLETED = 30
