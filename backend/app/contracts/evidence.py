"""Evidence package, immutable artifact, lineage, and access contracts."""

from typing import Literal

from pydantic import Field

from app.contracts.common import Identifier, JsonValue, Sha256, StrictModel, VersionedModel


class EvidenceArtifactRef(StrictModel):
    artifact_id: str = Field(pattern=r"^art_[a-z0-9_-]{8,127}$")
    artifact_kind: Literal[
        "raw_opensearch_result",
        "source_result_table",
        "calculation_table",
        "statistical_result",
        "chart_data",
        "internal_qa",
    ]
    media_type: Literal["application/json", "text/csv"]
    content_hash: Sha256
    byte_size: int = Field(ge=0)
    row_count: int | None = Field(default=None, ge=0)
    complete: bool = True
    approximate: bool = False
    source_ids: tuple[str, ...] = ()
    task_ids: tuple[Identifier, ...] = ()
    preview: JsonValue = None
    download_url: str


class SourceQueryEvidence(StrictModel):
    query_id: str
    query_plan_id: str
    query_step_id: Identifier
    dataset_id: Identifier
    indices: tuple[str, ...]
    time_range: dict[str, JsonValue]
    timezone: str
    filters: tuple[dict[str, JsonValue], ...] = ()
    dimensions: tuple[Identifier, ...] = ()
    grain: tuple[str, ...] = ()
    metrics: tuple[Identifier, ...] = ()
    measures: tuple[dict[str, JsonValue], ...] = ()
    query_fingerprint: str
    safe_query_summary: dict[str, JsonValue]
    execution_ids: tuple[str, ...]
    took_ms: int = Field(ge=0)
    page_count: int = Field(ge=1)
    bucket_count: int = Field(ge=0)
    row_count: int = Field(ge=0)
    complete: bool
    partial: bool
    raw_result_artifact: EvidenceArtifactRef | None = None
    source_table_artifact: EvidenceArtifactRef


class CalculationTableEvidence(StrictModel):
    calculation_id: Identifier
    table_id: str
    source_table_ids: tuple[str, ...]
    task_ids: tuple[Identifier, ...] = ()
    grain: tuple[str, ...]
    input_columns: tuple[str, ...]
    output_columns: tuple[str, ...]
    definition_ids: tuple[Identifier, ...] = ()
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    row_ids: tuple[str, ...] = ()
    content_hash: Sha256
    complete: bool
    approximate: bool = False
    artifact: EvidenceArtifactRef


class TechnicalDefinitionEvidence(StrictModel):
    definition_id: Identifier
    definition_type: Literal["metric", "measure", "method"]
    version: str
    display_name: str
    purpose_or_business_definition: str
    technical_expression: str
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ClaimTraceEvidence(StrictModel):
    claim_id: str
    task_ids: tuple[Identifier, ...] = ()
    text: str
    evidence_refs: tuple[dict[str, JsonValue], ...]
    definition_ids: tuple[Identifier, ...] = ()


class EvidenceQualitySummary(StrictModel):
    status: Literal["VALID", "WARNING", "BLOCKED"]
    material_warnings: tuple[str, ...] = ()
    blocked_reasons: tuple[str, ...] = ()
    completeness: tuple[str, ...] = ()
    reconciliation_summary: tuple[dict[str, JsonValue], ...] = ()
    internal_qa_artifact: EvidenceArtifactRef | None = None


class BusinessEvidence(StrictModel):
    scope: dict[str, JsonValue]
    source_queries: tuple[SourceQueryEvidence, ...] = ()
    source_results: tuple[EvidenceArtifactRef, ...] = ()
    calculated_tables: tuple[CalculationTableEvidence, ...] = ()
    technical_definitions: tuple[TechnicalDefinitionEvidence, ...] = ()
    claim_trace: tuple[ClaimTraceEvidence, ...] = ()
    quality_summary: EvidenceQualitySummary | None = None
    # Backward-compatible fields remain during the V6.1 snapshot migration. New UI uses
    # the structured sections above. ``quality`` is intentionally always empty for users.
    metric_definitions: tuple[dict[str, JsonValue], ...] = ()
    data_tables: tuple[str, ...] = ()
    reconciliations: tuple[dict[str, JsonValue], ...] = ()
    quality: tuple[dict[str, JsonValue], ...] = ()
    exploratory_analysis: tuple[dict[str, JsonValue], ...] = ()
    downloads: tuple[str, ...] = ()


class AdvancedEvidence(StrictModel):
    query_plan: dict[str, JsonValue]
    compiled_queries: tuple[dict[str, JsonValue], ...] = ()
    execution_summaries: tuple[dict[str, JsonValue], ...] = ()
    result_contracts: tuple[dict[str, JsonValue], ...] = ()
    artifacts: tuple[EvidenceArtifactRef, ...] = ()


class EvidenceRedaction(StrictModel):
    removed_fields: tuple[str, ...] = ()
    masked_fields: tuple[str, ...] = ()
    policy_id: str | None = None


class EvidencePackage(VersionedModel):
    business: BusinessEvidence
    advanced: AdvancedEvidence
    debug_ref: str | None = None
    redaction: EvidenceRedaction = Field(default_factory=EvidenceRedaction)
