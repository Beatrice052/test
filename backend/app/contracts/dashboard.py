"""Safe dashboard intent and rendering contracts."""

from typing import Literal

from pydantic import Field

from app.contracts.analysis import GovernedChartType
from app.contracts.common import Identifier, JsonScalar, JsonValue, StrictModel, VersionedModel


class VisualizationCandidate(StrictModel):
    candidate_id: Identifier
    analytical_question: str
    intent: str
    preferred_chart_types: tuple[GovernedChartType, ...]
    dataset_id: Identifier
    task_ids: tuple[Identifier, ...] = Field(min_length=1)
    dimension_roles: dict[str, str] = Field(default_factory=dict)
    measure_roles: dict[str, str] = Field(default_factory=dict)
    priority: Literal["required", "recommended", "optional"]
    reason: str


class VisualizationExplorationDraft(StrictModel):
    """Agent C's bounded request for chart previews, never executable code."""

    candidates: tuple[VisualizationCandidate, ...] = Field(default=(), max_length=20)
    dropped_candidate_ids: tuple[Identifier, ...] = ()
    limitations: tuple[str, ...] = ()


class VisualizationDefinition(StrictModel):
    visualization_id: Identifier
    version: str
    intent: str
    allowed_chart_types: tuple[GovernedChartType, ...]
    minimum_rows: int = Field(default=1, ge=0)
    maximum_categories: int = Field(default=20, ge=1)
    minimum_time_points: int = Field(default=1, ge=1)
    requires_complete_distribution: bool = False


class ChartEncoding(StrictModel):
    x: str | None = None
    y: str | None = None
    category: str | None = None
    value: str | None = None
    color: str | None = None
    series: str | None = None
    tooltip_fields: tuple[str, ...] = ()


class VisualProfile(StrictModel):
    """Deterministic facts returned by the visualization tool to Agent C."""

    row_count: int = Field(ge=0)
    category_count: int = Field(ge=0)
    series_count: int = Field(ge=0)
    time_point_count: int = Field(ge=0)
    visible_columns: tuple[str, ...]
    value_range: dict[str, JsonScalar] = Field(default_factory=dict)
    representative_rows: tuple[dict[str, JsonValue], ...] = ()


class VisualizationPreview(VersionedModel):
    """A governed chart preview produced by an Adapter, not by the LLM."""

    candidate_id: Identifier
    task_ids: tuple[Identifier, ...]
    analytical_question: str
    purpose: str
    dataset_id: Identifier
    visualization_intent: str
    decision: Literal["ACCEPT", "ACCEPT_WITH_TRANSFORM", "DOWNGRADE_TO_TABLE", "REJECT"]
    renderer: Literal["echarts_contract", "table"]
    chart_type: str | None = None
    encoding: ChartEncoding | None = None
    transforms: tuple[str, ...] = ()
    reason: str
    profile: VisualProfile
    evidence_row_ids: tuple[str, ...] = ()


class KpiItem(StrictModel):
    kpi_id: Identifier
    label: str
    value: JsonScalar
    formatted_value: str
    unit: str | None = None
    semantic_level: Literal["certified", "governed", "operational", "exploratory"]
    quality: Literal["valid", "insufficient_sample", "not_applicable"] = "valid"
    definition: str
    evidence_row_ids: tuple[str, ...] = ()


class ChartFinding(StrictModel):
    claim_id: Identifier
    text: str
    importance: Literal["primary", "secondary", "supporting"]
    evidence_row_ids: tuple[str, ...] = Field(min_length=1)


class ChartAnalysis(StrictModel):
    purpose: str
    reading_guide: str
    findings: tuple[ChartFinding, ...] = Field(min_length=1)
    caveats: tuple[str, ...] = ()


class DashboardBlock(StrictModel):
    block_id: Identifier
    type: Literal[
        "answer_summary",
        "context_summary",
        "kpi_group",
        "chart",
        "data_table",
        "pivot_table",
        "insight_list",
        "warning",
        "empty_state",
        "clarification",
        "follow_up_suggestions",
    ]
    title: str | None = None
    description: str | None = None
    dataset_id: Identifier | None = None
    visualization_intent: str | None = None
    chart_type: GovernedChartType | None = None
    encoding: ChartEncoding | None = None
    sort: tuple[str, ...] = ()
    stack: bool = False
    axis_format: dict[str, str] = Field(default_factory=dict)
    legend: bool = True
    chart_analysis: ChartAnalysis | None = None
    evidence_refs: tuple[str, ...] = ()
    kpis: tuple[KpiItem, ...] = ()
    insights: tuple[str, ...] = ()
    suggestions: tuple[str, ...] = ()
    content: dict[str, JsonValue] = Field(default_factory=dict)


class DashboardSpec(VersionedModel):
    title: str
    layout: Literal["auto_grid"] = "auto_grid"
    blocks: tuple[DashboardBlock, ...]
    warnings: tuple[str, ...] = ()
