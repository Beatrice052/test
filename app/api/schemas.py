from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatStatus(StrEnum):
    ANSWERED = "answered"
    NEEDS_CLARIFICATION = "needs_clarification"
    BLOCKED = "blocked"
    NOT_ANSWERABLE = "not_answerable"
    ERROR = "error"


class ChatRequest(ApiModel):
    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=20_000)

    @field_validator("session_id")
    @classmethod
    def normalize_session_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("session_id cannot be blank")
        if not all(character.isalnum() or character in "-_" for character in normalized):
            raise ValueError("session_id contains unsupported characters")
        return normalized

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("message cannot be blank")
        return normalized


class SessionResetRequest(ApiModel):
    session_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class SessionResetResponse(ApiModel):
    session_id: str
    status: Literal["reset"] = "reset"


class KpiItem(ApiModel):
    id: str
    label: str
    value: int | float | None
    display_value: str
    unit: str


class TableColumn(ApiModel):
    field: str
    label: str
    type: Literal["string", "integer", "number", "percent", "datetime"]


class TableData(ApiModel):
    columns: list[TableColumn] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class ChartData(ApiModel):
    type: Literal["bar", "line", "horizontal_bar", "grouped_bar"]
    title: str
    x_field: str
    y_field: str
    series_field: str | None = None
    data: list[dict[str, Any]] = Field(default_factory=list)


class MetricDefinition(ApiModel):
    metric_id: str
    metric_version: str
    status: Literal["POC_DEFINED", "BUSINESS_CONFIRMED"]


class EvidenceResponse(ApiModel):
    analysis_plan: dict[str, Any] = Field(default_factory=dict)
    field_resolution: dict[str, Any] = Field(default_factory=dict)
    query_plan: dict[str, Any] = Field(default_factory=dict)
    tool: str | None = None
    tool_reason_code: str | None = None
    query_dsl: dict[str, Any] = Field(default_factory=dict)
    raw_result_summary: dict[str, Any] = Field(default_factory=dict)
    chart_data: list[dict[str, Any]] = Field(default_factory=list)
    qa: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(ApiModel):
    session_id: str
    run_id: str | None = None
    status: ChatStatus
    assistant_message: str
    needs_clarification: bool = False
    clarification_question: str | None = None
    kpis: list[KpiItem] = Field(default_factory=list)
    table: TableData | None = None
    chart: ChartData | None = None
    metric_definition: MetricDefinition | None = None
    warnings: list[str] = Field(default_factory=list)
    evidence: EvidenceResponse | None = None
    reason_code: str | None = None


class HealthResponse(ApiModel):
    status: Literal["ok"] = "ok"
    app_name: str
    phase: str
    data_source_mode: Literal["mock", "mcp"]
    connection_status: Literal["mock", "connected", "disconnected"]
    index_scope: str
    default_time_from: str
    default_time_to: str
    business_timezone: str
    semantic_model_version: str
    capabilities: dict[str, bool]


class SemanticReportResponse(ApiModel):
    model_version: str
    import_status: str
    report: dict[str, Any]
