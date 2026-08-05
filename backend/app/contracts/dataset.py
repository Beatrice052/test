"""Normalized tabular datasets, QA, and lineage contracts."""

from enum import StrEnum
from typing import Literal

from pydantic import Field

from app.contracts.common import Identifier, JsonValue, StrictModel, VersionedModel
from app.contracts.query import BucketPathItem


class DatasetCompleteness(StrEnum):
    COMPLETE = "COMPLETE"
    TOP_N_WITH_OTHERS = "TOP_N_WITH_OTHERS"
    TRUNCATED = "TRUNCATED"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class DatasetColumn(StrictModel):
    name: str
    data_type: Literal["string", "integer", "number", "boolean", "datetime", "metric"]
    nullable: bool = False
    semantic_role: Literal["dimension", "measure", "metric", "metadata"]
    field_id: Identifier | None = None
    metric_id: Identifier | None = None
    measure_id: Identifier | None = None
    source_field_id: Identifier | None = None
    aggregation: str | None = None
    aggregation_name: str | None = None
    aggregation_result_path: str | None = None
    aggregation_parameters: dict[str, JsonValue] = Field(default_factory=dict)
    aggregation_semantics: str | None = None
    source_grain: tuple[Identifier, ...] = ()
    population_scope: str | None = None
    approximate: bool = False
    unit: str | None = None
    display_name: str | None = None
    semantic_type: str | None = None
    business_domain: str | None = None
    security_classification: Literal["public", "internal", "confidential", "restricted"] = (
        "internal"
    )


class DatasetContract(VersionedModel):
    dataset_id: Identifier
    grain: tuple[str, ...]
    dimensions: tuple[str, ...]
    metrics: tuple[Identifier, ...]
    measures: tuple[Identifier, ...] = ()
    primary_key: tuple[str, ...]
    expected_complete_dimensions: tuple[str, ...]
    columns: tuple[DatasetColumn, ...]
    bucket_path: tuple[BucketPathItem, ...]


class DatasetRow(StrictModel):
    row_id: str = Field(pattern=r"^row_[0-9a-f]{16}$")
    values: dict[str, JsonValue]


class TabularDataset(VersionedModel):
    dataset_id: Identifier
    contract_id: str
    kind: Literal["base", "derived"]
    grain: tuple[str, ...]
    columns: tuple[DatasetColumn, ...]
    rows: tuple[DatasetRow, ...]
    completeness: DatasetCompleteness
    complete: bool
    truncated: bool
    source_dataset_ids: tuple[Identifier, ...] = ()
    derivation_id: Identifier | None = None
    warnings: tuple[str, ...] = ()


class DataQARecord(StrictModel):
    rule_id: Identifier
    severity: Literal["INFO", "WARNING", "ERROR", "FATAL"]
    passed: bool
    message: str
    dataset_id: Identifier | None = None
    metric_id: Identifier | None = None
    evidence_row_ids: tuple[str, ...] = ()
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ReconciliationRecord(StrictModel):
    reconciliation_id: Identifier
    passed: bool
    expected: float | int | None
    actual: float | int | None
    tolerance: float = Field(default=0, ge=0)
    message: str
    dataset_ids: tuple[Identifier, ...]


class DatasetBundle(VersionedModel):
    datasets: tuple[TabularDataset, ...]
    data_qa: tuple[DataQARecord, ...] = ()
    reconciliation: tuple[ReconciliationRecord, ...] = ()
    complete: bool
    warnings: tuple[str, ...] = ()
