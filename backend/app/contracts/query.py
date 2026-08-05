"""Logical query plans and deterministic compiler output contracts."""

from enum import StrEnum
from typing import Literal

from pydantic import Field

from app.contracts.common import Identifier, JsonValue, StrictModel, TimeRange, VersionedModel
from app.contracts.metric import AggregationSpec


class QueryStepStatus(StrEnum):
    PLANNED = "PLANNED"
    COMPILED = "COMPILED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class QueryFilter(StrictModel):
    field_id: Identifier
    operator: Literal["eq", "in", "range", "exists", "not"]
    values: tuple[str | int | float | bool, ...] = ()


class ParameterBinding(StrictModel):
    parameter: Identifier
    source_dataset_contract: Identifier
    selection: Literal["top_n", "distinct", "scalar"]
    metric_id: Identifier | None = None
    n: int | None = Field(default=None, ge=1, le=100)


class QueryStep(StrictModel):
    step_id: Identifier
    purpose_task_ids: tuple[Identifier, ...]
    dataset_id: Identifier
    index_patterns: tuple[str, ...]
    time_range: TimeRange
    time_field_id: Identifier
    filters: tuple[QueryFilter, ...]
    dimensions: tuple[Identifier, ...]
    measures: tuple[Identifier, ...]
    field_measures: tuple[AggregationSpec, ...] = ()
    grain: tuple[str, ...]
    result_contract_id: Identifier
    depends_on: tuple[Identifier, ...] = ()
    parameter_bindings: tuple[ParameterBinding, ...] = ()
    estimated_buckets: int = Field(ge=0)
    timeout_ms: int = Field(default=30000, ge=100, le=120000)
    required: bool = True


class QueryPlanDraft(StrictModel):
    analysis_plan_id: str
    steps: tuple[QueryStep, ...]
    reuse_strategy: Literal["dataset_fingerprint"] = "dataset_fingerprint"
    consolidation_notes: tuple[str, ...] = ()


class QueryPlan(VersionedModel):
    analysis_plan_id: str
    steps: tuple[QueryStep, ...]
    reuse_strategy: Literal["dataset_fingerprint"] = "dataset_fingerprint"
    consolidation_notes: tuple[str, ...] = ()
    total_estimated_buckets: int = Field(ge=0)


class BucketPathItem(StrictModel):
    aggregation_name: str
    dimension_id: Identifier
    bucket_kind: Literal["terms", "composite", "date_histogram", "filters", "nested"]
    key_field: str | None = None


class QuerySemantics(StrictModel):
    dataset_id: Identifier
    time_range: TimeRange
    time_field_id: Identifier
    field_ids: tuple[Identifier, ...]
    metric_ids: tuple[Identifier, ...]
    field_measures: tuple[AggregationSpec, ...] = ()
    filter_fingerprint: str
    grain: tuple[str, ...]
    bucket_path: tuple[BucketPathItem, ...]


class CompiledQuery(VersionedModel):
    query_plan_id: str
    step_id: Identifier
    indices: tuple[str, ...]
    query_dsl: dict[str, JsonValue]
    semantics: QuerySemantics
    query_fingerprint: str
    timeout_ms: int
    result_contract_id: Identifier
