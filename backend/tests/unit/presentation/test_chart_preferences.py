"""Explicit chart requests are parsed and constrained by data relationships."""

import pytest

from app.contracts.dashboard import VisualizationCandidate, VisualizationDefinition
from app.llm.mock_chart_preferences import parse_chart_preference
from app.presentation.chart_preferences import (
    apply_candidate_preference,
)


@pytest.mark.parametrize(
    ("message", "expected"),
    (
        ("请用柱状图展示", "bar"),
        ("请改成折线图", "line"),
        ("展示堆叠柱状图", "stacked_bar"),
        ("我想看热力图", "heatmap"),
        ("用饼图看占比", "donut"),
        ("请给透视表", "pivot"),
        ("改成数据表", "table"),
        ("请用帕累托图", "pareto"),
    ),
)
def test_chart_type_aliases_are_recognized(message: str, expected: str) -> None:
    assert parse_chart_preference(message).chart_type == expected


def test_explicit_type_keeps_all_tasks_and_downgrades_incompatible_relationships() -> None:
    candidates = (
        VisualizationCandidate(
            candidate_id="trend",
            analytical_question="Trend",
            intent="time_trend",
            preferred_chart_types=("bar",),
            dataset_id="by_time",
            task_ids=("task_trend",),
            dimension_roles={"time": "occurred_at"},
            measure_roles={"value": "record_count"},
            priority="required",
            reason="trend",
        ),
        VisualizationCandidate(
            candidate_id="rank",
            analytical_question="Rank",
            intent="ranked_comparison",
            preferred_chart_types=("bar",),
            dataset_id="by_category",
            task_ids=("task_rank",),
            dimension_roles={"category": "region"},
            measure_roles={"value": "record_count"},
            priority="required",
            reason="rank",
        ),
    )
    definitions = (
        VisualizationDefinition(
            visualization_id="trend",
            version="v1",
            intent="time_trend",
            allowed_chart_types=("line", "bar"),
        ),
        VisualizationDefinition(
            visualization_id="rank",
            version="v1",
            intent="ranked_comparison",
            allowed_chart_types=("bar", "dot"),
        ),
    )

    selected, notes = apply_candidate_preference(
        candidates,
        definitions,
        parse_chart_preference("请只用折线图展示"),
    )

    assert [item.candidate_id for item in selected] == ["trend", "rank"]
    assert selected[0].preferred_chart_types[0] == "line"
    assert selected[1].preferred_chart_types == ("line",)
    assert any("不兼容" in item for item in notes)


def test_unsupported_type_is_recorded_without_inventing_a_renderer() -> None:
    preference = parse_chart_preference("请画雷达图")
    assert preference.unsupported
    selected, notes = apply_candidate_preference((), (), preference)
    assert selected == ()
    assert "安全图表目录" in notes[0]


def test_unimplemented_scatter_request_is_not_treated_as_a_safe_renderer() -> None:
    preference = parse_chart_preference("use a scatter plot")

    assert preference.chart_type is None
    assert preference.unsupported is True
    assert preference.user_label == "scatter plot"
