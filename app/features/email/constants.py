from enum import StrEnum


class EmailProcessingStatus(StrEnum):
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    SKIPPED = 'skipped'


class EmailApiErrorCode(StrEnum):
    SENDER_NOT_FOUND = 'SENDER_NOT_FOUND'
    MESSAGE_NOT_FOUND = 'MESSAGE_NOT_FOUND'
    SENDER_ALREADY_EXISTS = 'SENDER_ALREADY_EXISTS'
    INVALID_FILTER_PROCESSING_STATUS = 'INVALID_FILTER_PROCESSING_STATUS'
