"""Parse explicit user chart requests and apply them through the governed catalog."""

from __future__ import annotations

from dataclasses import dataclass

from app.contracts.dashboard import (
    DashboardBlock,
    VisualizationCandidate,
    VisualizationDefinition,
)


@dataclass(frozen=True, slots=True)
class ChartPreference:
    chart_type: str | None = None
    user_label: str | None = None
    unsupported: bool = False


_ALIASES: tuple[tuple[str, str], ...] = (
    ("堆叠柱状图", "stacked_bar"),
    ("堆叠条形图", "stacked_bar"),
    ("stacked bar", "stacked_bar"),
    ("热力图", "heatmap"),
    ("heatmap", "heatmap"),
    ("环形图", "donut"),
    ("圆环图", "donut"),
    ("donut", "donut"),
    ("饼图", "donut"),
    ("pie chart", "donut"),
    ("帕累托图", "pareto"),
    ("pareto chart", "pareto"),
    ("pareto", "pareto"),
    ("折线图", "line"),
    ("趋势线", "line"),
    ("line chart", "line"),
    ("柱状图", "bar"),
    ("条形图", "bar"),
    ("bar chart", "bar"),
    ("点图", "dot"),
    ("dot plot", "dot"),
    ("透视表", "pivot"),
    ("pivot table", "pivot"),
    ("表格展示", "table"),
    ("数据表", "table"),
    ("table", "table"),
)

_UNSUPPORTED_ALIASES = (
    "雷达图",
    "桑基图",
    "旭日图",
    "漏斗图",
    "箱线图",
    "地图",
    "radar chart",
    "sankey",
    "sunburst",
    "funnel chart",
    "box plot",
    "散点图",
    "scatter plot",
    "scatter",
)


def parse_chart_preference(message: str) -> ChartPreference:
    normalized = message.casefold()
    for label, chart_type in _ALIASES:
        if label.casefold() in normalized:
            return ChartPreference(chart_type=chart_type, user_label=label)
    for label in _UNSUPPORTED_ALIASES:
        if label.casefold() in normalized:
            return ChartPreference(user_label=label, unsupported=True)
    return ChartPreference()


def apply_candidate_preference(
    candidates: tuple[VisualizationCandidate, ...],
    definitions: tuple[VisualizationDefinition, ...],
    preference: ChartPreference,
) -> tuple[tuple[VisualizationCandidate, ...], tuple[str, ...]]:
    if preference.unsupported:
        return candidates, (
            f"用户指定的{preference.user_label}不在当前安全图表目录中, 已按数据关系自动选图。",
        )
    requested = preference.chart_type
    if requested is None:
        return candidates, ()
    if requested in {"table", "pivot"}:
        return (
            tuple(
                item.model_copy(update={"preferred_chart_types": (requested,)})
                for item in candidates
            ),
            (),
        )
    allowed_by_intent = {item.intent: set(item.allowed_chart_types) for item in definitions}
    compatible = tuple(
        item.model_copy(
            update={
                "preferred_chart_types": (
                    requested,
                    *(existing for existing in item.preferred_chart_types if existing != requested),
                )
            }
        )
        for item in candidates
        if requested in allowed_by_intent.get(item.intent, set())
        and _candidate_shape_supports(item, requested)
    )
    if compatible:
        return compatible, ()
    downgraded = tuple(
        item.model_copy(update={"preferred_chart_types": (requested,)}) for item in candidates
    )
    return downgraded, (
        f"用户指定的{preference.user_label or requested}与当前数据关系不兼容, 已降级为可核查表格。",
    )


def block_supports_chart_type(block: DashboardBlock, chart_type: str) -> bool:
    encoding = block.encoding
    if encoding is None:
        return False
    if chart_type == "line":
        return block.visualization_intent in {"time_trend", "anomaly"} and encoding.x is not None
    if chart_type in {"stacked_bar", "heatmap"}:
        return encoding.x is not None and encoding.series is not None and encoding.value is not None
    if chart_type == "donut":
        return encoding.category is not None and encoding.series is None
    if chart_type == "scatter":
        return encoding.x is not None and encoding.y is not None and encoding.x != encoding.y
    if chart_type in {"bar", "dot", "pareto"}:
        return encoding.category is not None and encoding.series is None
    return False


def _candidate_shape_supports(candidate: VisualizationCandidate, chart_type: str) -> bool:
    if chart_type == "line":
        return "time" in candidate.dimension_roles
    if chart_type in {"stacked_bar", "heatmap"}:
        return "series" in candidate.dimension_roles
    if chart_type == "donut":
        return "category" in candidate.dimension_roles and "series" not in candidate.dimension_roles
    if chart_type == "scatter":
        return {"x", "y"}.issubset(candidate.measure_roles)
    if chart_type in {"bar", "dot", "pareto"}:
        return "category" in candidate.dimension_roles and "series" not in candidate.dimension_roles
    return False
