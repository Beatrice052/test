"""Claims are fully grounded and dashboards remain declarative and data-driven."""

from pathlib import Path
from typing import Any, cast

import pytest

from app.analytics.bundle import DatasetBundleBuilder
from app.analytics.derivation import StatusMetricDeriver
from app.contracts.dashboard import VisualizationCandidate
from app.contracts.dataset import DataQARecord, DatasetColumn
from app.contracts.insight import ClaimBinding, ClaimDraft, InsightDashboardDraft
from app.orchestration.phase5_nodes import Phase5Nodes
from app.presentation.dashboard import ChartFeasibilityValidator, DashboardBuilder
from app.presentation.grounding import ClaimGrounder
from app.semantic.package import CompiledSemanticPackage
from tests.integration.query.test_plan_compile import _plans
from tests.unit.analytics.test_metric_qa import _base_dataset, _derive

PACKAGE_DIR = Path(__file__).parents[4] / "compiled-semantic" / "mock"


def _bundle(*qa: DataQARecord):
    derived = _derive()
    return DatasetBundleBuilder().build(
        (derived.dataset,),
        data_qa=qa,
        reconciliation=derived.reconciliation,
    )


def test_argmax_and_ratio_claims_bind_to_exact_rows_and_metric_evidence() -> None:
    bundle = _bundle()
    dataset_id = bundle.datasets[0].dataset_id
    result = ClaimGrounder().ground(
        (
            ClaimDraft(
                claim_type="ranking",
                template="{channel} has the highest count: {value}.",
                importance="primary",
                bindings=(
                    ClaimBinding(
                        name="channel",
                        dataset_id=dataset_id,
                        selector="argmax:message_record_count.v1",
                        column="channel",
                    ),
                    ClaimBinding(
                        name="value",
                        dataset_id=dataset_id,
                        selector="argmax:message_record_count.v1",
                        column="message_record_count.v1",
                    ),
                ),
            ),
            ClaimDraft(
                claim_type="value",
                template="SMS failure rate is {value}.",
                bindings=(
                    ClaimBinding(
                        name="value",
                        dataset_id=dataset_id,
                        selector="where:channel=SMS",
                        column="failure_rate.v1",
                    ),
                ),
            ),
        ),
        bundle,
    )
    assert result.failures == ()
    assert len(result.claims) == 2
    assert result.claims[0].text == "SMS has the highest count: 100."
    assert result.claims[0].evidence_refs[0].row_id == result.claims[0].evidence_refs[1].row_id
    assert result.claims[1].text == "SMS failure rate is 22.22%."
    assert result.claims[1].evidence_refs[0].metric_id == "failure_rate"


@pytest.mark.asyncio
async def test_required_analysis_tasks_need_explicit_grounded_claim_coverage() -> None:
    _, analysis, _, _, _, _ = await _plans("查询2026年7月各Channel失败率")
    bundle = _bundle()
    draft = ClaimDraft(
        claim_type="ranking",
        template="Top value is {value}.",
        importance="primary",
        bindings=(
            ClaimBinding(
                name="value",
                dataset_id="channel_metrics",
                selector="argmax:message_record_count.v1",
                column="message_record_count.v1",
            ),
        ),
    )
    grounding = ClaimGrounder().ground((draft,), bundle)
    state = cast(Any, {"analysis_plan": analysis, "dataset_bundle": bundle})

    missing = Phase5Nodes._claim_completeness_errors(
        state, InsightDashboardDraft(answer_summary="draft", claims=(draft,)), grounding
    )

    required = tuple(item.task_id for item in analysis.tasks if item.priority == "required")
    assert any("MISSING_REQUIRED_TASK" in item for item in missing)
    covered_draft = draft.model_copy(update={"task_ids": required})
    covered_grounding = ClaimGrounder().ground((covered_draft,), bundle)
    assert (
        Phase5Nodes._claim_completeness_errors(
            state,
            InsightDashboardDraft(answer_summary="draft", claims=(covered_draft,)),
            covered_grounding,
        )
        == ()
    )


def test_ambiguous_causal_and_qa_blocked_claims_are_deleted() -> None:
    bundle = _bundle(
        DataQARecord(
            rule_id="qa_total_reconcile",
            severity="ERROR",
            passed=False,
            message="totals differ",
            dataset_id="channel_metrics",
        )
    )
    blocked = ClaimDraft(
        claim_type="value",
        template="SMS caused the increase: {value}.",
        bindings=(
            ClaimBinding(
                name="value",
                dataset_id="channel_metrics",
                selector="where:channel=SMS",
                column="message_record_count.v1",
            ),
        ),
    )
    result = ClaimGrounder().ground((blocked,), bundle)
    assert result.claims == ()
    assert len(result.failures) == 1


def test_dashboard_accepts_useful_chart_deduplicates_and_has_no_raw_option() -> None:
    bundle = _bundle()
    definitions = CompiledSemanticPackage(PACKAGE_DIR).visualizations()
    candidate = VisualizationCandidate(
        candidate_id="vc_channel_rank",
        analytical_question="Compare channel record counts",
        intent="ranked_comparison",
        preferred_chart_types=("bar",),
        dataset_id="channel_metrics",
        dimension_roles={"category": "channel"},
        measure_roles={"value": "message_record_count.v1"},
        priority="required",
        reason="Useful ranking",
    )
    claims = (
        ClaimGrounder()
        .ground(
            (
                ClaimDraft(
                    claim_type="ranking",
                    template="Top value is {value}.",
                    bindings=(
                        ClaimBinding(
                            name="value",
                            dataset_id="channel_metrics",
                            selector="argmax:message_record_count.v1",
                            column="message_record_count.v1",
                        ),
                    ),
                ),
            ),
            bundle,
        )
        .claims
    )
    dashboard = DashboardBuilder(ChartFeasibilityValidator(definitions)).build(
        title="Channel overview",
        answer_summary="Validated channel comparison.",
        candidates=(candidate, candidate.model_copy(update={"candidate_id": "vc_duplicate"})),
        claims=claims,
        bundle=bundle,
        max_blocks=8,
    )
    charts = [item for item in dashboard.blocks if item.type == "chart"]
    assert len(charts) == 1
    assert charts[0].chart_type == "bar"
    assert charts[0].axis_format == {"value": "number"}
    assert charts[0].evidence_refs == tuple(item.row_id for item in bundle.datasets[0].rows)
    assert not any(item.type == "insight_list" for item in dashboard.blocks)
    assert not any(item.type == "data_table" for item in dashboard.blocks)
    summary = dashboard.blocks[0]
    assert summary.insights == ("Top value is 100.",)
    serialized = dashboard.model_dump_json()
    assert "raw_option" not in serialized
    assert "javascript" not in serialized


def test_chart_is_rejected_when_encoding_omits_a_grain_dimension() -> None:
    bundle = _bundle()
    source = bundle.datasets[0]
    first = source.rows[0]
    too_detailed = source.model_copy(
        update={
            "grain": ("month", "channel"),
            "columns": (
                DatasetColumn(
                    name="month",
                    data_type="datetime",
                    nullable=False,
                    semantic_role="dimension",
                    semantic_type="time_dimension",
                ),
                *source.columns,
            ),
            "rows": (
                first.model_copy(
                    update={
                        "row_id": "row_month_1",
                        "values": {**first.values, "month": "2026-05-01T00:00:00Z"},
                    }
                ),
                first.model_copy(
                    update={
                        "row_id": "row_month_2",
                        "values": {
                            **first.values,
                            "month": "2026-06-01T00:00:00Z",
                            "record_count": int(first.values["record_count"]) + 1,
                            "message_record_count.v1": int(first.values["message_record_count.v1"])
                            + 1,
                        },
                    }
                ),
            ),
        }
    )
    candidate = VisualizationCandidate(
        candidate_id="vc_hidden_grain",
        analytical_question="Rank categories",
        intent="ranked_comparison",
        preferred_chart_types=("bar",),
        dataset_id=too_detailed.dataset_id,
        dimension_roles={"category": "channel"},
        measure_roles={"value": "message_record_count.v1"},
        priority="required",
        reason="ranking",
    )
    result = ChartFeasibilityValidator(
        CompiledSemanticPackage(PACKAGE_DIR).visualizations()
    ).validate(candidate, bundle.model_copy(update={"datasets": (too_detailed,)}))

    assert result.decision.value == "DOWNGRADE_TO_TABLE"
    assert "complete Dataset grain" in result.reason


def test_chart_is_rejected_for_duplicate_rows_at_declared_grain() -> None:
    bundle = _bundle()
    source = bundle.datasets[0]
    duplicated = source.model_copy(
        update={
            "rows": (
                source.rows[0],
                source.rows[0].model_copy(update={"row_id": "row_duplicate"}),
                *source.rows[1:],
            )
        }
    )
    candidate = VisualizationCandidate(
        candidate_id="vc_duplicate_grain",
        analytical_question="Rank categories",
        intent="ranked_comparison",
        preferred_chart_types=("bar",),
        dataset_id=duplicated.dataset_id,
        dimension_roles={"category": "channel"},
        measure_roles={"value": "message_record_count.v1"},
        priority="required",
        reason="ranking",
    )
    result = ChartFeasibilityValidator(
        CompiledSemanticPackage(PACKAGE_DIR).visualizations()
    ).validate(candidate, bundle.model_copy(update={"datasets": (duplicated,)}))

    assert result.decision.value == "DOWNGRADE_TO_TABLE"
    assert "duplicate rows" in result.reason


def test_high_cardinality_chart_downgrades_without_fake_frontend_top_n() -> None:
    bundle = _bundle()
    source = bundle.datasets[0]
    seed = source.rows[0]
    rows = tuple(
        seed.model_copy(
            update={
                "row_id": f"row_category_{index}",
                "values": {
                    **seed.values,
                    "sub_message.channel": f"CHANNEL_{index:02d}",
                    "message_record_count.v1": index + 1,
                },
            }
        )
        for index in range(40)
    )
    candidate = VisualizationCandidate(
        candidate_id="vc_high_cardinality",
        analytical_question="Rank all channels",
        intent="ranked_comparison",
        preferred_chart_types=("bar",),
        dataset_id=source.dataset_id,
        dimension_roles={"category": "channel"},
        measure_roles={"value": "message_record_count.v1"},
        priority="required",
        reason="ranking",
    )
    result = ChartFeasibilityValidator(
        CompiledSemanticPackage(PACKAGE_DIR).visualizations()
    ).validate(
        candidate,
        bundle.model_copy(update={"datasets": (source.model_copy(update={"rows": rows}),)}),
    )

    assert result.decision.value == "DOWNGRADE_TO_TABLE"
    assert "governed chart limit" in result.reason
    assert result.transforms == ()


def test_no_visual_candidate_keeps_technical_detail_out_of_dashboard() -> None:
    bundle = _bundle(
        DataQARecord(
            rule_id="qa_small_sample",
            severity="WARNING",
            passed=False,
            message="one or more metric samples are below minimum size",
            dataset_id="channel_metrics",
        )
    )
    dashboard = DashboardBuilder(
        ChartFeasibilityValidator(CompiledSemanticPackage(PACKAGE_DIR).visualizations())
    ).build(
        title="Fallback",
        answer_summary="Validated data is available.",
        candidates=(),
        claims=(),
        bundle=bundle,
        max_blocks=3,
    )
    assert [item.type for item in dashboard.blocks] == ["answer_summary"]
    assert bundle.warnings == dashboard.warnings


def test_multiple_useful_charts_reuse_one_dataset_and_constant_chart_is_removed() -> None:
    bundle = _bundle()
    definitions = CompiledSemanticPackage(PACKAGE_DIR).visualizations()
    rank = VisualizationCandidate(
        candidate_id="vc_rank_reuse",
        analytical_question="Rank channels",
        intent="ranked_comparison",
        preferred_chart_types=("bar",),
        dataset_id="channel_metrics",
        dimension_roles={"category": "channel"},
        measure_roles={"value": "message_record_count.v1"},
        priority="required",
        reason="ranking",
    )
    composition = rank.model_copy(
        update={
            "candidate_id": "vc_composition_reuse",
            "intent": "composition",
            "preferred_chart_types": ("donut",),
            "reason": "composition",
        }
    )
    dashboard = DashboardBuilder(ChartFeasibilityValidator(definitions)).build(
        title="Reuse",
        answer_summary="Two useful views.",
        candidates=(rank, composition),
        claims=(),
        bundle=bundle,
        max_blocks=5,
    )
    chart_datasets = [item.dataset_id for item in dashboard.blocks if item.type == "chart"]
    assert chart_datasets == [bundle.datasets[0].object_id, bundle.datasets[0].object_id]
    assert len(bundle.datasets) == 1

    dataset = bundle.datasets[0]
    constant_rows = tuple(
        row.model_copy(update={"values": {**row.values, "message_record_count.v1": 10}})
        for row in dataset.rows
    )
    constant_bundle = bundle.model_copy(
        update={"datasets": (dataset.model_copy(update={"rows": constant_rows}),)}
    )
    low_value = DashboardBuilder(ChartFeasibilityValidator(definitions)).build(
        title="Low value",
        answer_summary="Constant data.",
        candidates=(rank,),
        claims=(),
        bundle=constant_bundle,
        max_blocks=3,
    )
    assert not any(item.type == "chart" for item in low_value.blocks)
    assert not any(item.type == "data_table" for item in low_value.blocks)


def test_requested_table_is_a_business_result_not_a_technical_detail() -> None:
    bundle = _bundle()
    candidate = VisualizationCandidate(
        candidate_id="vc_requested_table",
        analytical_question="Compare channel record counts",
        intent="ranked_comparison",
        preferred_chart_types=("table",),
        dataset_id="channel_metrics",
        dimension_roles={"category": "sub_message.channel"},
        measure_roles={"value": "message_record_count.v1"},
        priority="required",
        reason="The user requested a table",
    )
    dashboard = DashboardBuilder(
        ChartFeasibilityValidator(CompiledSemanticPackage(PACKAGE_DIR).visualizations())
    ).build(
        title="Table result",
        answer_summary="Validated result.",
        candidates=(candidate,),
        claims=(),
        bundle=bundle,
        max_blocks=3,
    )

    table = next(item for item in dashboard.blocks if item.type == "data_table")
    assert table.title == "Compare channel record counts"
    assert table.title != "聚合明细与指标口径"


def test_pareto_transform_is_computed_by_the_deterministic_backend() -> None:
    bundle = _bundle()
    candidate = VisualizationCandidate(
        candidate_id="vc_backend_pareto",
        analytical_question="Find concentrated channel contribution",
        intent="pareto",
        preferred_chart_types=("pareto",),
        dataset_id="channel_metrics",
        dimension_roles={"category": "channel"},
        measure_roles={"value": "message_record_count.v1"},
        priority="recommended",
        reason="concentration analysis",
    )
    dashboard = DashboardBuilder(
        ChartFeasibilityValidator(CompiledSemanticPackage(PACKAGE_DIR).visualizations())
    ).build(
        title="Pareto",
        answer_summary="Validated result.",
        candidates=(candidate,),
        claims=(),
        bundle=bundle,
        max_blocks=3,
    )

    chart = next(item for item in dashboard.blocks if item.type == "chart")
    points = chart.content["pareto_points"]
    assert isinstance(points, list)
    point_items = [item for item in points if isinstance(item, dict)]
    assert [item["category"] for item in point_items] == ["SMS", "SMALL", "EMAIL"]
    assert [item["cumulative_percent"] for item in point_items] == [
        85.470085,
        95.726496,
        100.0,
    ]


def test_kpis_only_promote_metrics_selected_by_the_analysis_plan() -> None:
    package = CompiledSemanticPackage(PACKAGE_DIR)
    overall = StatusMetricDeriver().derive(
        _base_dataset(),
        output_dataset_id="overall_metrics",
        derivation_id="derive_overall_metrics.v1",
        group_by=(),
        status_field_id="sub_message.status",
        value_dictionary=package.values()[0],
        metric_definitions=package.metrics(),
    )
    bundle = DatasetBundleBuilder().build((overall.dataset,))
    builder = DashboardBuilder(
        ChartFeasibilityValidator(package.visualizations()),
        package.metrics(),
    )

    dashboard = builder.build(
        title="Failure quality",
        answer_summary="Validated result.",
        candidates=(),
        claims=(),
        bundle=bundle,
        max_blocks=3,
        kpi_metric_ids=("failure_rate.v1",),
    )

    kpi_block = next(item for item in dashboard.blocks if item.type == "kpi_group")
    assert [item.label for item in kpi_block.kpis] == ["失败率"]
    assert not any("排除占比" in item.label for item in kpi_block.kpis)
