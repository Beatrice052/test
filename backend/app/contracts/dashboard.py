"""Safe dashboard intent and rendering contracts."""

from typing import Literal

from pydantic import Field

from app.contracts.common import Identifier, JsonScalar, JsonValue, StrictModel, VersionedModel


class VisualizationCandidate(StrictModel):
    candidate_id: Identifier
    analytical_question: str
    intent: str
    preferred_chart_types: tuple[str, ...]
    dataset_id: Identifier
    dimension_roles: dict[str, str] = Field(default_factory=dict)
    measure_roles: dict[str, str] = Field(default_factory=dict)
    priority: Literal["required", "recommended", "optional"]
    reason: str


class VisualizationDefinition(StrictModel):
    visualization_id: Identifier
    version: str
    intent: str
    allowed_chart_types: tuple[str, ...]
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
    chart_type: (
        Literal[
            "bar",
            "line",
            "heatmap",
            "stacked_bar",
            "donut",
            "dot",
            "pareto",
            "table",
            "pivot",
        ]
        | None
    ) = None
    encoding: ChartEncoding | None = None
    sort: tuple[str, ...] = ()
    stack: bool = False
    axis_format: dict[str, str] = Field(default_factory=dict)
    legend: bool = True
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
