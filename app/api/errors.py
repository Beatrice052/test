from __future__ import annotations

from enum import StrEnum


class ReasonCode(StrEnum):
    PHASE_NOT_IMPLEMENTED = "PHASE_NOT_IMPLEMENTED"
    INVALID_REQUEST = "INVALID_REQUEST"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    NOT_ANSWERABLE = "NOT_ANSWERABLE"
    INDEX_NOT_AVAILABLE = "INDEX_NOT_AVAILABLE"
    QUERY_VALIDATION_FAILED = "QUERY_VALIDATION_FAILED"
    DATA_QUALITY_FAILED = "DATA_QUALITY_FAILED"
    EXECUTION_FAILED = "EXECUTION_FAILED"


class ChatBIError(Exception):
    def __init__(self, message: str, reason_code: ReasonCode) -> None:
        super().__init__(message)
        self.message = message
        self.reason_code = reason_code
