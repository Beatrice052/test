"""Agent-C statistical requests are validated and executed by host code."""

from pathlib import Path

import pytest

from app.analytics.bundle import DatasetBundleBuilder
from app.analytics.features import FeatureSummaryBuilder
from app.analytics.governed_tool import GovernedAnalyticsTool
from app.contracts.insight import AnalyticsToolRequest
from tests.integration.query.test_plan_compile import _plans
from tests.unit.analytics.test_metric_qa import _derive

PACKAGE_DIR = Path(__file__).parents[4] / "compiled-semantic" / "mock"


@pytest.mark.asyncio
async def test_agent_c_can_choose_a_registered_method_and_governed_metric_column() -> None:
    package, plan, _, _, _, _ = await _plans("查询2026年7月各Channel失败率")
    derived = _derive()
    bundle = DatasetBundleBuilder().build((derived.dataset,), reconciliation=derived.reconciliation)
    summaries = (FeatureSummaryBuilder().build(derived.dataset),)
    task_id = next(item.task_id for item in plan.tasks if item.priority == "required")

    execution = GovernedAnalyticsTool(package.methods()).execute(
        (
            AnalyticsToolRequest(
                request_id="analysis_failure_rate_rank",
                task_ids=(task_id,),
                dataset_id=derived.dataset.dataset_id,
                method_id="rank",
                measure_column="failure_rate.v1",
                purpose="Compare the observed failure-rate values across available groups.",
            ),
        ),
        analysis_plan=plan,
        bundle=bundle,
        feature_summaries=summaries,
    )

    result = execution.results[0]
    assert result.decision == "APPLICABLE"
    assert result.result.values["column"] == "failure_rate.v1"
    assert execution.feature_summaries[0].statistical_results[0].method_id == "rank"
    assert (
        execution.feature_summaries[0].statistical_results[0].values["column"] == "failure_rate.v1"
    )


@pytest.mark.asyncio
async def test_unregistered_method_is_retained_as_an_auditable_nonresult() -> None:
    package, plan, _, _, _, _ = await _plans("查询2026年7月各Channel失败率")
    derived = _derive()
    bundle = DatasetBundleBuilder().build((derived.dataset,), reconciliation=derived.reconciliation)
    task_id = next(item.task_id for item in plan.tasks if item.priority == "required")

    execution = GovernedAnalyticsTool(package.methods()).execute(
        (
            AnalyticsToolRequest(
                request_id="analysis_unknown_method",
                task_ids=(task_id,),
                dataset_id=derived.dataset.dataset_id,
                method_id="invented_method",
                measure_column="message_record_count.v1",
                purpose="This must not become an untracked calculation.",
            ),
        ),
        analysis_plan=plan,
        bundle=bundle,
        feature_summaries=(FeatureSummaryBuilder().build(derived.dataset),),
    )

    assert execution.results[0].decision == "REJECTED"
    assert execution.results[0].result.applicability == "NOT_APPLICABLE"
    assert "unregistered" in execution.results[0].reason
