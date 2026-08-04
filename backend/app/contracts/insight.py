"""Post-query feature, claim draft, and grounded claim contracts."""

from typing import Literal

from pydantic import Field

from app.contracts.common import Identifier, JsonValue, StrictModel, VersionedModel


class StatisticalResult(StrictModel):
    method_id: Identifier
    version: str
    applicability: Literal["APPLICABLE", "NOT_APPLICABLE"]
    sample_size: int = Field(ge=0)
    values: dict[str, JsonValue] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    exploratory: bool = True


class FeatureSummary(VersionedModel):
    dataset_id: Identifier
    row_count: int = Field(ge=0)
    columns: tuple[str, ...]
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


class InsightDashboardDraft(StrictModel):
    answer_summary: str
    claims: tuple[ClaimDraft, ...] = ()
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
