from enum import IntEnum, StrEnum


class NatTaskStatus(IntEnum):
    CANCELLED = -20
    QUEUED = -1
    LAUNCHED = 10
    IN_PROGRESS = 20
    COMPLETED = 30


class NatIpFieldName(StrEnum):
    INTERNAL_IP = 'internal_ip'
    EXTERNAL_IP = 'external_ip'
    RESOURCE_IP = 'resource_ip'
