"""Apply Agent A's structured chart preference through the governed catalog."""

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
    compatible: list[VisualizationCandidate] = []
    incompatible_found = False
    for item in candidates:
        if requested in allowed_by_intent.get(item.intent, set()) and _candidate_shape_supports(
            item, requested
        ):
            compatible.append(
                item.model_copy(
                    update={
                        "preferred_chart_types": (
                            requested,
                            *(
                                existing
                                for existing in item.preferred_chart_types
                                if existing != requested
                            ),
                        )
                    }
                )
            )
        else:
            incompatible_found = True
            compatible.append(item.model_copy(update={"preferred_chart_types": (requested,)}))
    notes = (
        (
            (
                f"用户指定的{preference.user_label or requested}与部分数据关系不兼容, "
                "相应视图已降级为可核查表格。"
            ),
        )
        if incompatible_found
        else ()
    )
    return tuple(compatible), notes


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
