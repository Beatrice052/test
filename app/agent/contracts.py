from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AnalysisType(StrEnum):
    COUNT = "count"
    FILTERED_COUNT = "filtered_count"
    TERMS_BREAKDOWN = "terms_breakdown"
    DATE_HISTOGRAM = "date_histogram"
    TOP_N = "top_n"
    TWO_DIMENSION_BREAKDOWN = "two_dimension_breakdown"
    SIMPLE_NUMERIC_AGGREGATION = "simple_numeric_aggregation"
    METRIC_SUMMARY = "metric_summary"
    METRIC_BREAKDOWN = "metric_breakdown"
    METRIC_TREND = "metric_trend"
    PERIOD_COMPARISON = "period_comparison"


class RequestedOutput(StrEnum):
    KPI = "kpi"
    TABLE = "table"
    CHART = "chart"
    SUMMARY = "summary"


class TimeRange(StrictModel):
    type: str
    from_: datetime = Field(alias="from")
    to: datetime
    grain: Literal["hour", "day", "week", "month"] | None = None

    @model_validator(mode="after")
    def validate_half_open_range(self) -> TimeRange:
        if self.from_.tzinfo is None or self.to.tzinfo is None:
            raise ValueError("time range must be timezone-aware")
        if self.from_ >= self.to:
            raise ValueError("time range must satisfy from < to")
        return self


class FilterConcept(StrictModel):
    concept: str
    operator: Literal["eq", "in", "range"]
    values: list[str | int | float | bool | None]


class AnalysisPlan(StrictModel):
    """Describes the requested analysis, never execution mechanics."""

    analysis_type: AnalysisType
    dataset_concept: str = "sub_message"
    metric_concepts: list[str] = Field(default_factory=list)
    dimension_concepts: list[str] = Field(default_factory=list)
    filter_concepts: list[FilterConcept] = Field(default_factory=list)
    time_range: TimeRange
    comparison: dict[str, Any] | None = None
    requested_outputs: list[RequestedOutput] = Field(default_factory=list)


class QueryFilter(StrictModel):
    field: str
    operator: Literal["term", "terms", "range"]
    values: list[str | int | float | bool | None]


class GroupBy(StrictModel):
    kind: Literal["terms", "date_histogram"]
    field: str
    size: int | None = Field(default=None, gt=0)
    interval: str | None = None


class QueryLimits(StrictModel):
    max_buckets: int = Field(default=2000, gt=0)
    timeout_seconds: int = Field(default=30, gt=0)
    max_top_n: int = Field(default=50, gt=0)


class QueryPlan(StrictModel):
    """Physical data plan that deliberately contains neither Tool nor DSL."""

    query_id: str
    dataset_id: str
    physical_indices: list[str] = Field(min_length=1)
    query_type: AnalysisType
    time_filter: dict[str, Any]
    filters: list[QueryFilter] = Field(default_factory=list)
    group_by: list[GroupBy] = Field(default_factory=list)
    metric_refs: list[str] = Field(default_factory=list)
    independent_tasks: int = Field(default=1, gt=0)
    limits: QueryLimits = Field(default_factory=QueryLimits)


class EvidenceBundle(StrictModel):
    run_id: str
    question: str
    semantic_model_version: str
    analysis_plan: dict[str, Any] = Field(default_factory=dict)
    field_resolution: dict[str, Any] = Field(default_factory=dict)
    metric_versions: dict[str, str] = Field(default_factory=dict)
    answerability: dict[str, Any] = Field(default_factory=dict)
    query_plans: list[dict[str, Any]] = Field(default_factory=list)
    compiled_queries: list[dict[str, Any]] = Field(default_factory=list)
    execution_records: list[dict[str, Any]] = Field(default_factory=list)
    prepared_data: dict[str, Any] = Field(default_factory=dict)
    chart_specs: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
