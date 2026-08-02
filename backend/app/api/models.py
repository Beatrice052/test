"""Closed request and response envelopes for the HTTP API."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.contracts.common import JsonValue, StrictModel
from app.contracts.dataset import DatasetColumn, DatasetRow
from app.contracts.evidence import AdvancedEvidence, BusinessEvidence, EvidenceRedaction
from app.contracts.progress import AnalysisProgressEvent
from app.contracts.session import AnswerSnapshot, SessionContext


class SessionCreateRequest(StrictModel):
    title: str = Field(default="New analysis", min_length=1, max_length=256)


class SessionPatchRequest(StrictModel):
    title: str = Field(min_length=1, max_length=256)
    expected_version: int = Field(ge=0)


class SessionDetailResponse(StrictModel):
    session: SessionContext
    answers: tuple[AnswerSnapshot, ...]


class ChatApiResponse(StrictModel):
    status: str
    session_id: str
    turn_id: str
    answer: AnswerSnapshot | None = None


class ChatProgressEnvelope(StrictModel):
    event: Literal["progress"] = "progress"
    progress: AnalysisProgressEvent


class ChatResultEnvelope(StrictModel):
    event: Literal["result"] = "result"
    result: ChatApiResponse


class ChatErrorEnvelope(StrictModel):
    event: Literal["error"] = "error"
    code: str
    message: str


class TurnResponse(StrictModel):
    turn_id: str
    session_id: str
    client_turn_id: str
    attempt: int
    status: str
    retryable: bool
    created_at: datetime
    updated_at: datetime
    error: dict[str, JsonValue] | None = None


class EvidenceView(StrictModel):
    evidence_id: str
    business: BusinessEvidence
    advanced: AdvancedEvidence | None = None
    redaction: EvidenceRedaction


class DatasetRowsResponse(StrictModel):
    object_id: str
    dataset_id: str
    kind: str
    grain: tuple[str, ...]
    columns: tuple[DatasetColumn, ...]
    rows: tuple[DatasetRow, ...]
    offset: int
    limit: int
    total: int
    complete: bool
    warnings: tuple[str, ...]


class SemanticPackageResponse(StrictModel):
    package_version: str
    manifest_hash: str
    field_count: int
    metric_count: int
    generated_at: datetime


class SemanticCompileRequest(StrictModel):
    profile: str = Field(default="configured", pattern=r"^configured$")
