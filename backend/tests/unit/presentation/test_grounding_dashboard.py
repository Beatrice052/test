"""Claims are fully grounded and dashboards remain declarative and data-driven."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from app.analytics.bundle import DatasetBundleBuilder
from app.analytics.derivation import StatusMetricDeriver
from app.analytics.features import FeatureSummaryBuilder
from app.analytics.identity import stable_row_id
from app.contracts.common import Provenance, semantic_hash
from app.contracts.dashboard import VisualizationCandidate
from app.contracts.dataset import (
    DataQARecord,
    DatasetColumn,
    DatasetCompleteness,
    DatasetRow,
    TabularDataset,
)
from app.contracts.insight import (
    ClaimBinding,
    ClaimDraft,
    InsightDashboardDraft,
    StatisticalResult,
    VisualInsightDraft,
)
from app.orchestration.phase5_nodes import Phase5Nodes
from app.presentation.dashboard import ChartFeasibilityValidator, DashboardBuilder
from app.presentation.exploration import GovernedVisualizationExplorer
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


def _preview_bundle(candidates: tuple[VisualizationCandidate, ...], bundle: Any) -> tuple[Any, ...]:
    validator = ChartFeasibilityValidator(CompiledSemanticPackage(PACKAGE_DIR).visualizations())
    return GovernedVisualizationExplorer(validator).explore(candidates, bundle)


def _visual_insights(previews: tuple[Any, ...], claim_id: str) -> tuple[VisualInsightDraft, ...]:
    return tuple(
        VisualInsightDraft(
            insight_id=f"insight_{index}",
            preview_id=preview.object_id,
            claim_ids=(claim_id,),
            purpose=preview.purpose,
        )
        for index, preview in enumerate(previews)
    )


def test_argmax_and_ratio_claims_bind_to_exact_rows_and_metric_evidence() -> None:
    bundle = _bundle()
    dataset_id = bundle.datasets[0].dataset_id
    result = ClaimGrounder().ground(
        (
            ClaimDraft(
                claim_id="claim_count_rank",
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
                claim_id="claim_sms_failure_rate",
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


def test_statistical_claims_bind_to_deterministic_method_result_and_source_rows() -> None:
    bundle = _bundle()
    dataset = bundle.datasets[0]
    statistical_result = StatisticalResult(
        method_id="trend_slope",
        version="1.0.0",
        applicability="APPLICABLE",
        sample_size=len(dataset.rows),
        values={
            "column": "message_record_count.v1",
            "slope_per_period": 12.5,
            "first_row_id": dataset.rows[0].row_id,
            "last_row_id": dataset.rows[-1].row_id,
        },
    )
    summary = FeatureSummaryBuilder().build(
        dataset,
        statistical_results=(statistical_result,),
    )

    result = ClaimGrounder().ground(
        (
            ClaimDraft(
                claim_id="claim_trend_slope",
                claim_type="trend",
                template="The verified slope is {slope} per period.",
                importance="primary",
                bindings=(
                    ClaimBinding(
                        name="slope",
                        dataset_id=dataset.dataset_id,
                        selector="statistic:trend_slope",
                        column="slope_per_period",
                    ),
                ),
            ),
        ),
        bundle,
        feature_summaries=(summary,),
    )

    assert result.failures == ()
    assert result.claims[0].text == "The verified slope is 12.5 per period."
    evidence = result.claims[0].evidence_refs
    assert {item.row_id for item in evidence} == {
        dataset.rows[0].row_id,
        dataset.rows[-1].row_id,
    }
    assert {item.column for item in evidence} == {"message_record_count.v1"}
    assert {item.statistical_method_id for item in evidence} == {"trend_slope"}
    assert {item.statistical_result_hash for item in evidence} == {
        semantic_hash(statistical_result)
    }


def test_statistical_claim_rejects_unknown_or_non_scalar_value_path() -> None:
    bundle = _bundle()
    dataset = bundle.datasets[0]
    summary = FeatureSummaryBuilder().build(
        dataset,
        statistical_results=(
            StatisticalResult(
                method_id="trend_slope",
                version="1.0.0",
                applicability="APPLICABLE",
                sample_size=len(dataset.rows),
                values={
                    "column": "message_record_count.v1",
                    "details": {"slope": 2.0},
                },
            ),
        ),
    )
    draft = ClaimDraft(
        claim_id="claim_invalid_stat_path",
        claim_type="trend",
        template="Value {value}",
        bindings=(
            ClaimBinding(
                name="value",
                dataset_id=dataset.dataset_id,
                selector="statistic:trend_slope",
                column="details",
            ),
        ),
    )

    result = ClaimGrounder().ground((draft,), bundle, feature_summaries=(summary,))

    assert result.claims == ()
    assert "not scalar" in result.failures[0].message


def test_statistical_selector_disambiguates_same_method_across_metrics() -> None:
    bundle = _bundle()
    dataset = bundle.datasets[0]
    summary = FeatureSummaryBuilder().build(
        dataset,
        statistical_results=(
            StatisticalResult(
                method_id="rank",
                version="v1",
                applicability="APPLICABLE",
                sample_size=len(dataset.rows),
                values={"column": "message_record_count.v1", "top": [{"value": 100.0}]},
            ),
            StatisticalResult(
                method_id="rank",
                version="v1",
                applicability="APPLICABLE",
                sample_size=len(dataset.rows),
                values={"column": "failure_rate.v1", "top": [{"value": 0.25}]},
            ),
        ),
    )
    draft = ClaimDraft(
        claim_id="claim_metric_specific_rank",
        claim_type="ranking",
        template="Top failure rate is {value}.",
        bindings=(
            ClaimBinding(
                name="value",
                dataset_id=dataset.dataset_id,
                selector="statistic:rank@failure_rate.v1",
                column="top.0.value",
            ),
        ),
    )

    result = ClaimGrounder().ground((draft,), bundle, feature_summaries=(summary,))

    assert result.failures == ()
    assert result.claims[0].text == "Top failure rate is 25.00%."
    ambiguous = draft.model_copy(
        update={"bindings": (draft.bindings[0].model_copy(update={"selector": "statistic:rank"}),)}
    )
    rejected = ClaimGrounder().ground((ambiguous,), bundle, feature_summaries=(summary,))
    assert "ambiguous" in rejected.failures[0].message


@pytest.mark.asyncio
async def test_required_analysis_tasks_need_explicit_grounded_claim_coverage() -> None:
    _, analysis, _, _, _, _ = await _plans("查询2026年7月各Channel失败率")
    bundle = _bundle()
    draft = ClaimDraft(
        claim_id="claim_required_coverage",
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
        state, InsightDashboardDraft(answer_summary="draft", claims=(draft,)), grounding, ()
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
            (),
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
        claim_id="claim_blocked_causal",
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


def test_claims_without_unique_evidence_bindings_are_rejected() -> None:
    bundle = _bundle()
    dataset_id = bundle.datasets[0].dataset_id
    no_evidence = ClaimDraft(
        claim_id="claim_without_evidence",
        claim_type="value",
        template="This sentence has no evidence.",
        bindings=(),
    )
    duplicate_names = ClaimDraft(
        claim_id="claim_duplicate_binding_names",
        claim_type="comparison",
        template="Values are {value}.",
        bindings=(
            ClaimBinding(
                name="value",
                dataset_id=dataset_id,
                selector="where:channel=SMS",
                column="message_record_count.v1",
            ),
            ClaimBinding(
                name="value",
                dataset_id=dataset_id,
                selector="where:channel=EMAIL",
                column="message_record_count.v1",
            ),
        ),
    )

    result = ClaimGrounder().ground((no_evidence, duplicate_names), bundle)

    assert result.claims == ()
    assert "at least one evidence binding" in result.failures[0].message
    assert "binding names are not unique" in result.failures[1].message


def test_dashboard_accepts_useful_chart_deduplicates_and_has_no_raw_option() -> None:
    bundle = _bundle()
    candidate = VisualizationCandidate(
        candidate_id="vc_channel_rank",
        analytical_question="Compare channel record counts",
        intent="ranked_comparison",
        preferred_chart_types=("bar",),
        dataset_id="channel_metrics",
        task_ids=("task_rank",),
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
                    claim_id="claim_chart_rank",
                    claim_type="ranking",
                    template="Top value is {value}.",
                    task_ids=("task_rank",),
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
    previews = _preview_bundle(
        (candidate, candidate.model_copy(update={"candidate_id": "vc_duplicate"})), bundle
    )
    dashboard = DashboardBuilder().build(
        title="Channel overview",
        answer_summary="Validated channel comparison.",
        previews=previews,
        visual_insights=_visual_insights(previews, "claim_chart_rank"),
        claims=claims,
        bundle=bundle,
        max_blocks=8,
    )
    charts = [item for item in dashboard.blocks if item.type == "chart"]
    assert len(charts) == 1
    assert charts[0].chart_type == "bar"
    assert charts[0].axis_format == {"value": "number"}
    assert charts[0].chart_analysis is not None
    assert charts[0].chart_analysis.purpose == "Useful ranking"
    assert charts[0].chart_analysis.findings[0].claim_id == "claim_chart_rank"
    assert "比较" in charts[0].chart_analysis.reading_guide
    assert charts[0].evidence_refs == tuple(item.row_id for item in bundle.datasets[0].rows)
    assert not any(item.type == "insight_list" for item in dashboard.blocks)
    assert not any(item.type == "data_table" for item in dashboard.blocks)
    summary = dashboard.blocks[0]
    assert summary.insights == ("Top value is 100.",)
    serialized = dashboard.model_dump_json()
    assert "raw_option" not in serialized
    assert "javascript" not in serialized


def test_chart_cannot_reuse_a_claim_bound_to_a_different_measure() -> None:
    bundle = _bundle()
    candidate = VisualizationCandidate(
        candidate_id="vc_count_chart",
        analytical_question="Compare record counts",
        intent="ranked_comparison",
        preferred_chart_types=("bar",),
        dataset_id="channel_metrics",
        task_ids=("task_count",),
        dimension_roles={"category": "channel"},
        measure_roles={"value": "message_record_count.v1"},
        priority="required",
        reason="Compare count",
    )
    claims = (
        ClaimGrounder()
        .ground(
            (
                ClaimDraft(
                    claim_id="claim_failure_rate_only",
                    claim_type="ranking",
                    template="Top failure rate is {value}.",
                    task_ids=("task_count",),
                    bindings=(
                        ClaimBinding(
                            name="value",
                            dataset_id="channel_metrics",
                            selector="argmax:failure_rate.v1",
                            column="failure_rate.v1",
                        ),
                    ),
                ),
            ),
            bundle,
        )
        .claims
    )
    previews = _preview_bundle((candidate,), bundle)
    dashboard = DashboardBuilder().build(
        title="Wrong measure binding",
        answer_summary="Validated result.",
        previews=previews,
        visual_insights=_visual_insights(previews, "claim_failure_rate_only"),
        claims=claims,
        bundle=bundle,
        max_blocks=4,
    )

    assert not any(item.type == "chart" for item in dashboard.blocks)


def test_same_intent_can_render_distinct_governed_measures_without_false_dedup() -> None:
    bundle = _bundle()
    count_candidate = VisualizationCandidate(
        candidate_id="vc_count_rank",
        analytical_question="Rank record counts",
        intent="ranked_comparison",
        preferred_chart_types=("bar",),
        dataset_id="channel_metrics",
        task_ids=("task_count",),
        dimension_roles={"category": "channel"},
        measure_roles={"value": "message_record_count.v1"},
        priority="required",
        reason="Count ranking",
    )
    rate_candidate = count_candidate.model_copy(
        update={
            "candidate_id": "vc_rate_rank",
            "analytical_question": "Rank failure rates",
            "task_ids": ("task_rate",),
            "measure_roles": {"value": "failure_rate.v1"},
            "reason": "Rate ranking",
        }
    )
    claim_drafts = (
        ClaimDraft(
            claim_id="claim_count",
            claim_type="ranking",
            template="Highest count is {value}.",
            task_ids=("task_count",),
            bindings=(
                ClaimBinding(
                    name="value",
                    dataset_id="channel_metrics",
                    selector="argmax:message_record_count.v1",
                    column="message_record_count.v1",
                ),
            ),
        ),
        ClaimDraft(
            claim_id="claim_rate",
            claim_type="ranking",
            template="Highest failure rate is {value}.",
            task_ids=("task_rate",),
            bindings=(
                ClaimBinding(
                    name="value",
                    dataset_id="channel_metrics",
                    selector="argmax:failure_rate.v1",
                    column="failure_rate.v1",
                ),
            ),
        ),
    )
    claims = ClaimGrounder().ground(claim_drafts, bundle).claims
    previews = _preview_bundle((count_candidate, rate_candidate), bundle)
    insights = (
        VisualInsightDraft(
            insight_id="insight_count",
            preview_id=previews[0].object_id,
            claim_ids=("claim_count",),
            purpose="Compare counts",
        ),
        VisualInsightDraft(
            insight_id="insight_rate",
            preview_id=previews[1].object_id,
            claim_ids=("claim_rate",),
            purpose="Compare rates",
        ),
    )
    dashboard = DashboardBuilder().build(
        title="Two measures",
        answer_summary="Validated result.",
        previews=previews,
        visual_insights=insights,
        claims=claims,
        bundle=bundle,
        max_blocks=5,
    )

    charts = [item for item in dashboard.blocks if item.type == "chart"]
    assert [item.encoding.value for item in charts if item.encoding is not None] == [
        "message_record_count.v1",
        "failure_rate.v1",
    ]


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
        task_ids=("task_rank",),
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
        task_ids=("task_rank",),
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
        task_ids=("task_rank",),
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
    dashboard = DashboardBuilder().build(
        title="Fallback",
        answer_summary="Validated data is available.",
        previews=(),
        visual_insights=(),
        claims=(),
        bundle=bundle,
        max_blocks=3,
    )
    assert [item.type for item in dashboard.blocks] == ["answer_summary"]
    assert bundle.warnings == dashboard.warnings


def test_multiple_useful_charts_reuse_one_dataset_and_constant_chart_is_removed() -> None:
    bundle = _bundle()
    rank = VisualizationCandidate(
        candidate_id="vc_rank_reuse",
        analytical_question="Rank channels",
        intent="ranked_comparison",
        preferred_chart_types=("bar",),
        dataset_id="channel_metrics",
        task_ids=("task_rank",),
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
    chart_claims = (
        ClaimGrounder()
        .ground(
            (
                ClaimDraft(
                    claim_id="claim_reused_dataset",
                    claim_type="ranking",
                    template="Top value is {value}.",
                    task_ids=("task_rank",),
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
    previews = _preview_bundle((rank, composition), bundle)
    dashboard = DashboardBuilder().build(
        title="Reuse",
        answer_summary="Two useful views.",
        previews=previews,
        visual_insights=_visual_insights(previews, "claim_reused_dataset"),
        claims=chart_claims,
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
    constant_previews = _preview_bundle((rank,), constant_bundle)
    low_value = DashboardBuilder().build(
        title="Low value",
        answer_summary="Constant data.",
        previews=constant_previews,
        visual_insights=_visual_insights(constant_previews, "claim_reused_dataset"),
        claims=chart_claims,
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
        task_ids=("task_table",),
        dimension_roles={"category": "sub_message.channel"},
        measure_roles={"value": "message_record_count.v1"},
        priority="required",
        reason="The user requested a table",
    )
    table_claims = (
        ClaimGrounder()
        .ground(
            (
                ClaimDraft(
                    claim_id="claim_table_rank",
                    claim_type="ranking",
                    template="Top value is {value}.",
                    task_ids=("task_table",),
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
    previews = _preview_bundle((candidate,), bundle)
    dashboard = DashboardBuilder().build(
        title="Table result",
        answer_summary="Validated result.",
        previews=previews,
        visual_insights=_visual_insights(previews, "claim_table_rank"),
        claims=table_claims,
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
        task_ids=("task_pareto",),
        dimension_roles={"category": "channel"},
        measure_roles={"value": "message_record_count.v1"},
        priority="recommended",
        reason="concentration analysis",
    )
    pareto_claims = (
        ClaimGrounder()
        .ground(
            (
                ClaimDraft(
                    claim_id="claim_pareto_rank",
                    claim_type="ranking",
                    template="Top value is {value}.",
                    task_ids=("task_pareto",),
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
    previews = _preview_bundle((candidate,), bundle)
    dashboard = DashboardBuilder().build(
        title="Pareto",
        answer_summary="Validated result.",
        previews=previews,
        visual_insights=_visual_insights(previews, "claim_pareto_rank"),
        claims=pareto_claims,
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
    builder = DashboardBuilder(package.metrics())

    dashboard = builder.build(
        title="Failure quality",
        answer_summary="Validated result.",
        previews=(),
        visual_insights=(),
        claims=(),
        bundle=bundle,
        max_blocks=3,
        kpi_metric_ids=("failure_rate.v1",),
    )

    kpi_block = next(item for item in dashboard.blocks if item.type == "kpi_group")
    assert [item.label for item in kpi_block.kpis] == ["失败率"]
    assert not any("排除占比" in item.label for item in kpi_block.kpis)


def test_visual_profile_samples_endpoints_and_extrema_from_long_results() -> None:
    rows = tuple(
        DatasetRow(
            row_id=stable_row_id("long_result", ("category",), {"category": f"C{index}"}),
            values={
                "category": f"C{index}",
                "measure": 10_000 if index == 17 else -50 if index == 5 else index,
            },
        )
        for index in range(30)
    )
    dataset = TabularDataset(
        object_id="ds_long_result_deadbeef",
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        content_hash=semantic_hash([item.model_dump(mode="json") for item in rows]),
        provenance=Provenance(producer="tests.presentation"),
        dataset_id="long_result",
        contract_id="dc_long_result",
        kind="derived",
        grain=("category",),
        columns=(
            DatasetColumn(
                name="category",
                data_type="string",
                semantic_role="dimension",
            ),
            DatasetColumn(
                name="measure",
                data_type="number",
                semantic_role="metric",
            ),
        ),
        rows=rows,
        completeness=DatasetCompleteness.COMPLETE,
        complete=True,
        truncated=False,
    )
    bundle = DatasetBundleBuilder().build((dataset,))
    candidate = VisualizationCandidate(
        candidate_id="candidate_long_result",
        analytical_question="Which categories differ?",
        intent="ranked_comparison",
        preferred_chart_types=("bar",),
        dataset_id="long_result",
        task_ids=("task_long_result",),
        dimension_roles={"category": "category"},
        measure_roles={"value": "measure"},
        priority="required",
        reason="Inspect the full result shape",
    )

    preview = _preview_bundle((candidate,), bundle)[0]
    sampled_categories = {row["category"] for row in preview.profile.representative_rows}
    assert len(preview.profile.representative_rows) <= 12
    assert {"C0", "C5", "C17", "C29"}.issubset(sampled_categories)


@pytest.mark.asyncio
async def test_visual_explorer_rejects_agent_c_candidates_outside_agent_a_tasks() -> None:
    package, analysis, _, _, _, _ = await _plans("查询2026年7月各Channel失败率")
    bundle = _bundle()
    candidate = VisualizationCandidate(
        candidate_id="candidate_unknown_task",
        analytical_question="Unknown task",
        intent="ranked_comparison",
        preferred_chart_types=("bar",),
        dataset_id=bundle.datasets[0].dataset_id,
        task_ids=("task_not_in_analysis_plan",),
        dimension_roles={"category": "sub_message.channel"},
        measure_roles={"value": "message_record_count.v1"},
        priority="required",
        reason="Must be rejected",
    )
    validator = ChartFeasibilityValidator(package.visualizations())

    preview = GovernedVisualizationExplorer(validator).explore(
        (candidate,), bundle, analysis_plan=analysis
    )[0]

    assert preview.decision == "REJECT"
    assert "unknown tasks" in preview.reason


def test_visual_explorer_rejects_duplicate_candidate_ids() -> None:
    bundle = _bundle()
    candidate = VisualizationCandidate(
        candidate_id="candidate_duplicate",
        analytical_question="Compare values",
        intent="ranked_comparison",
        preferred_chart_types=("bar",),
        dataset_id=bundle.datasets[0].dataset_id,
        task_ids=("task_rank",),
        dimension_roles={"category": "channel"},
        measure_roles={"value": "message_record_count.v1"},
        priority="required",
        reason="Candidate identities must be unambiguous",
    )

    with pytest.raises(ValueError, match="candidate IDs are not unique"):
        _preview_bundle((candidate, candidate), bundle)


def test_agent_c_failure_dashboard_keeps_a_business_result_table() -> None:
    bundle = _bundle()
    dashboard = DashboardBuilder().build(
        title="Fallback",
        answer_summary="A grounded fallback answer.",
        previews=(),
        visual_insights=(),
        claims=(),
        bundle=bundle,
        max_blocks=1,
        ensure_result_table=True,
    )

    assert [item.type for item in dashboard.blocks] == ["answer_summary", "data_table"]
    assert dashboard.blocks[1].dataset_id == bundle.datasets[0].object_id
