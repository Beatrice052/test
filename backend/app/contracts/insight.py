"""Post-query feature, claim draft, and grounded claim contracts."""

from typing import Literal

from pydantic import Field

from app.contracts.common import Identifier, JsonScalar, JsonValue, StrictModel, VersionedModel


class StatisticalResult(StrictModel):
    result_id: Identifier | None = None
    method_id: Identifier
    version: str
    applicability: Literal["APPLICABLE", "NOT_APPLICABLE"]
    sample_size: int = Field(ge=0)
    values: dict[str, JsonValue] = Field(default_factory=dict)
    value_paths: tuple[str, ...] = ()
    calculation_table_id: Identifier | None = None
    warnings: tuple[str, ...] = ()
    exploratory: bool = True


class AnalyticsToolRequest(StrictModel):
    """Agent C's bounded request to a deterministic statistical-analysis tool.

    The request deliberately references an already validated Dataset column and a
    registered method.  It is not executable code and cannot introduce a business
    formula, query, physical field, or renderer specification.
    """

    request_id: Identifier
    task_ids: tuple[Identifier, ...] = Field(min_length=1)
    dataset_id: Identifier
    method_id: Identifier
    measure_column: str = Field(min_length=1)
    partition_columns: tuple[str, ...] = ()
    category_column: str | None = None
    time_column: str | None = None
    parameters: dict[str, JsonScalar] = Field(default_factory=dict)
    purpose: str = Field(min_length=1, max_length=500)


class AnalyticsToolResult(VersionedModel):
    """Auditable result returned by the host's governed analytics tool."""

    request_id: Identifier
    task_ids: tuple[Identifier, ...]
    dataset_id: Identifier
    method_id: Identifier
    measure_column: str
    partition_columns: tuple[str, ...] = ()
    category_column: str | None = None
    time_column: str | None = None
    decision: str
    result: StatisticalResult
    reason: str


class FeatureSummary(VersionedModel):
    dataset_id: Identifier
    row_count: int = Field(ge=0)
    columns: tuple[str, ...]
    task_ids: tuple[Identifier, ...] = ()
    grain: tuple[str, ...] = ()
    completeness: str | None = None
    top_rows: tuple[dict[str, JsonValue], ...] = ()
    bottom_rows: tuple[dict[str, JsonValue], ...] = ()
    totals: dict[str, JsonValue] = Field(default_factory=dict)
    ranges: dict[str, JsonValue] = Field(default_factory=dict)
    time_features: dict[str, JsonValue] = Field(default_factory=dict)
    statistical_results: tuple[StatisticalResult, ...] = ()
    qa_summary: dict[str, int] = Field(default_factory=dict)
    sample_rows: tuple[dict[str, JsonValue], ...] = ()


class ClaimBinding(StrictModel):
    name: Identifier
    dataset_id: Identifier
    selector: str
    column: str


class ClaimDraft(StrictModel):
    claim_id: Identifier
    claim_type: Literal["value", "ranking", "comparison", "trend", "share", "anomaly"]
    template: str
    importance: Literal["primary", "secondary", "supporting"] = "secondary"
    task_ids: tuple[Identifier, ...] = ()
    bindings: tuple[ClaimBinding, ...]


class VisualInsightDraft(StrictModel):
    """A final insight and its selected preview are authored together by Agent C."""

    insight_id: Identifier
    preview_id: Identifier
    claim_ids: tuple[Identifier, ...] = Field(min_length=1)
    purpose: str
    caveats: tuple[str, ...] = ()


class KpiSelectionDraft(StrictModel):
    """Agent C's post-analysis request to surface one already computed KPI."""

    selection_id: Identifier
    dataset_id: Identifier
    measure_column: str = Field(min_length=1)
    task_ids: tuple[Identifier, ...] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=500)


class InsightDashboardDraft(StrictModel):
    """Agent C pass-2 output.

    ``overall_claim_ids`` identifies the grounded claims that form the answer-first
    synthesis.  Chart-local selections stay explicit in ``VisualInsightDraft`` so
    DashboardBuilder never has to infer chart meaning; an indispensable fact may
    intentionally appear in both places without creating a separate key-findings page.
    """

    answer_summary: str
    claims: tuple[ClaimDraft, ...] = ()
    overall_claim_ids: tuple[Identifier, ...] = ()
    kpi_selections: tuple[KpiSelectionDraft, ...] = ()
    visual_insights: tuple[VisualInsightDraft, ...] = ()
    dropped_preview_ids: tuple[Identifier, ...] = ()
    limitations: tuple[str, ...] = ()
    follow_up_suggestions: tuple[str, ...] = ()
    fallback_requested: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)


class EvidenceRef(StrictModel):
    dataset_id: Identifier
    row_id: str
    column: str
    metric_id: Identifier | None = None
    statistical_method_id: Identifier | None = None
    statistical_result_hash: str | None = None


class ClaimSpec(VersionedModel):
    source_claim_id: Identifier | None = None
    claim_type: str
    text: str
    importance: Literal["primary", "secondary", "supporting"]
    task_ids: tuple[Identifier, ...] = ()
    evidence_refs: tuple[EvidenceRef, ...]
