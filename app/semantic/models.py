from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SemanticModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldAccess(StrEnum):
    ALLOWED = "allowed"
    REVIEW_REQUIRED = "review_required"
    BLOCKED = "blocked"


class SemanticMaturity(StrEnum):
    MAPPING_ONLY = "MAPPING_ONLY"
    DOCUMENTED = "DOCUMENTED"
    PROFILED = "PROFILED"
    BUSINESS_CONFIRMED = "BUSINESS_CONFIRMED"
    BLOCKED = "BLOCKED"


class CanonicalField(SemanticModel):
    field_path: str
    physical_aggregation_path: str | None = None
    mapping_type: str
    searchable: bool
    aggregatable: bool
    description: str = ""
    remarks: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    field_group_hint: str | None = None
    value_dictionary: dict[str, str] = Field(default_factory=dict)
    usage_guidance: list[str] = Field(default_factory=list)
    analysis_caveats: list[str] = Field(default_factory=list)
    semantic_maturity: SemanticMaturity
    sensitivity: str = "INTERNAL"
    access: FieldAccess
    allowed_operations: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    synthetic: bool = True


class MetricDefinition(SemanticModel):
    metric_id: str
    version: str
    status: str
    unit: str
    description: str = ""
    aggregation: str | None = None
    numerator_metric: str | None = None
    denominator_metric: str | None = None
    lifecycle_field: str | None = None
    success_values: list[str] = Field(default_factory=list)
    failed_values: list[str] = Field(default_factory=list)
    normalization: str | None = None
    formula: str | None = None
    zero_denominator: float | None = None
    rounding_digits: int = 2
    caveats: list[str] = Field(default_factory=list)


class QueryPolicy(SemanticModel):
    policy_version: str
    dataset_id: str
    index_pattern: str
    read_only: bool
    max_time_range_days: int
    max_month_partitions: int
    max_top_n: int
    max_buckets: int
    max_detail_size: int
    timeout_seconds: int
    allow_scripts: bool
    allow_generic_api: bool
    allow_raw_details: bool
    blocked_fields: list[str] = Field(default_factory=list)
    review_required_fields: list[str] = Field(default_factory=list)


class DatasetDefinition(SemanticModel):
    dataset_id: str
    index_pattern: str
    default_time_field: str
    business_timezone: str


class CompiledSemanticModel(SemanticModel):
    model_version: str
    dataset: DatasetDefinition
    fields: list[CanonicalField]
    metrics: list[MetricDefinition]
    value_dictionaries: dict[str, dict[str, str]]
    policy: QueryPolicy
    mapping_hash: str
    catalog_hash: str
    metric_hash: str
    policy_hash: str

    def field_map(self) -> dict[str, CanonicalField]:
        return {field.field_path: field for field in self.fields}

    def metric_map(self) -> dict[str, MetricDefinition]:
        return {metric.metric_id: metric for metric in self.metrics}


class ImportReport(SemanticModel):
    mapping_field_count: int
    catalog_row_count: int
    matched_count: int
    mapping_only_fields: list[str] = Field(default_factory=list)
    catalog_only_fields: list[str] = Field(default_factory=list)
    type_conflicts: list[dict[str, str]] = Field(default_factory=list)
    duplicate_field_paths: list[str] = Field(default_factory=list)
    invalid_metric_bindings: list[str] = Field(default_factory=list)
    blocked_fields: list[str] = Field(default_factory=list)
    review_required_fields: list[str] = Field(default_factory=list)
    ignored_columns: list[str] = Field(default_factory=lambda: ["candidate_role"])
    status: str
    source_summary: dict[str, Any] = Field(default_factory=dict)


class CompilationResult(SemanticModel):
    model: CompiledSemanticModel
    report: ImportReport


class FieldCandidate(SemanticModel):
    concept: str
    field_path: str
    score: float
    matched_on: list[str]
    mapping_type: str
    allowed_operations: list[str]
    semantic_maturity: SemanticMaturity
    caveats: list[str] = Field(default_factory=list)
