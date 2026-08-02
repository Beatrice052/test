"""Stable, redacted error contracts."""

from pydantic import Field

from app.contracts.common import JsonValue, StrictModel

ERROR_CODE_PATTERN = (
    r"^(REQ|AUTH|SEM|PLAN|QUERY|GW|RESULT|METRIC|QA|PRES|"
    r"SESSION|SEC|INTERNAL)_[A-Z0-9_]+$"
)


class ErrorDetail(StrictModel):
    code: str
    message: str
    context: dict[str, JsonValue] = Field(default_factory=dict)


class StructuredError(StrictModel):
    code: str = Field(pattern=ERROR_CODE_PATTERN)
    message: str
    correlation_id: str
    retryable: bool
    details: tuple[ErrorDetail, ...] = ()
    suggested_action: str | None = None
