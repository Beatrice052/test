"""Safe, user-visible progress events for an analytical turn."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.contracts.common import JsonValue, StrictModel

type AnalysisProgressStage = Literal[
    "request",
    "guardrails",
    "context",
    "intent",
    "query_plan",
    "dsl",
    "search",
    "analytics",
    "dashboard",
    "complete",
]
type AnalysisProgressStatus = Literal["running", "completed"]


class AnalysisProgressEvent(StrictModel):
    """An auditable stage update; never a model chain-of-thought payload."""

    sequence: int = Field(ge=1)
    stage: AnalysisProgressStage
    status: AnalysisProgressStatus
    title: str = Field(min_length=1, max_length=96)
    detail: str = Field(min_length=1, max_length=320)
    safe_summary: dict[str, JsonValue] = Field(default_factory=dict)
    occurred_at: datetime
