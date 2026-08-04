"""Agent C receives only bounded governed summaries and emits selector-based drafts."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.agents.base import AgentRuntime
from app.agents.insight_dashboard import InsightDashboardAgent
from app.analytics.bundle import DatasetBundleBuilder
from app.analytics.features import FeatureSummaryBuilder
from app.contracts.dashboard import VisualizationExplorationDraft
from app.contracts.insight import ClaimBinding, ClaimDraft, InsightDashboardDraft
from app.llm.fixture import FixtureLLMClient
from app.llm.rule_based import RuleBasedMockLLMClient
from tests.integration.query.test_plan_compile import _plans
from tests.unit.analytics.test_metric_qa import _derive

ROOT = Path(__file__).parents[3]
PACKAGE_DIR = ROOT.parent / "compiled-semantic" / "mock"
PROMPT = ROOT / "app" / "agents" / "prompts" / "insight_dashboard.md"
FIXTURE = ROOT.parent / "fixtures" / "llm" / "analysis_plans.json"


class CaptureInsightClient:
    def __init__(self) -> None:
        self.payload: dict[str, object] | None = None

    async def generate(
        self, **kwargs: Any
    ) -> InsightDashboardDraft | VisualizationExplorationDraft:
        self.payload = kwargs["input_payload"]
        if kwargs["output_schema"] is VisualizationExplorationDraft:
            return VisualizationExplorationDraft()
        return InsightDashboardDraft(
            answer_summary="Validated data is ready.",
            fallback_requested=True,
        )


async def _inputs():
    package, analysis, _, _, _, _ = await _plans("查询2026年7月各Channel失败率")
    derived = _derive()
    bundle = DatasetBundleBuilder().build((derived.dataset,), reconciliation=derived.reconciliation)
    features = (FeatureSummaryBuilder().build(derived.dataset),)
    return package, analysis, bundle, features


@pytest.mark.asyncio
async def test_agent_c_payload_has_schema_and_feature_summary_but_no_full_rows_or_query() -> None:
    package, analysis, bundle, features = await _inputs()
    client = CaptureInsightClient()
    agent = InsightDashboardAgent(
        AgentRuntime(llm=client, system_prompt=PROMPT.read_text(encoding="utf-8"))
    )
    await agent.plan(
        analysis_plan=analysis,
        bundle=bundle,
        feature_summaries=features,
        metric_definitions=package.metrics(),
        visualization_definitions=package.visualizations(),
        visualization_previews=(),
        correlation_id="cor_agent_c_capture",
    )
    assert client.payload is not None
    serialized = json.dumps(client.payload, ensure_ascii=False)
    assert "dataset_schemas" in client.payload
    assert "feature_summaries" in client.payload
    assert '"rows"' not in json.dumps(client.payload["dataset_schemas"])
    for forbidden in ("query_dsl", "raw_results", "compiled_queries", "MCP", "tool_bindings"):
        assert forbidden not in serialized


@pytest.mark.asyncio
async def test_rule_based_agent_c_uses_selectors_and_never_constructs_row_ids() -> None:
    package, analysis, bundle, features = await _inputs()
    client = RuleBasedMockLLMClient()
    draft = await InsightDashboardAgent(
        AgentRuntime(llm=client, system_prompt=PROMPT.read_text(encoding="utf-8"))
    ).plan(
        analysis_plan=analysis,
        bundle=bundle,
        feature_summaries=features,
        metric_definitions=package.metrics(),
        visualization_definitions=package.visualizations(),
        visualization_previews=(),
        correlation_id="cor_agent_c_rule",
    )
    assert draft.claims
    assert all(binding.selector for claim in draft.claims for binding in claim.bindings)
    assert "row_" not in draft.model_dump_json()
    assert client.calls[-1] == "post_query_insight_dashboard"


@pytest.mark.asyncio
async def test_checked_in_agent_c_fixture_interpolates_list_paths() -> None:
    client = FixtureLLMClient.from_file(FIXTURE)
    draft = await client.generate(
        operation="post_query_insight_dashboard",
        system_prompt="fixture",
        input_payload={"feature_summaries": [{"dataset_id": "q1_base_metrics"}]},
        output_schema=InsightDashboardDraft,
        timeout_seconds=1,
        correlation_id="cor_agent_c_fixture",
    )
    assert draft.claims[0].bindings[0].dataset_id == "q1_base_metrics"


@pytest.mark.asyncio
async def test_agent_c_directed_repair_is_bounded_to_schema_ids_without_rows() -> None:
    _, analysis, bundle, _ = await _inputs()
    client = CaptureInsightClient()
    agent = InsightDashboardAgent(
        AgentRuntime(llm=client, system_prompt=PROMPT.read_text(encoding="utf-8"))
    )
    draft = InsightDashboardDraft(
        answer_summary="draft",
        claims=(
            ClaimDraft(
                claim_id="claim_missing_column",
                claim_type="value",
                template="Value {value}",
                bindings=(
                    ClaimBinding(
                        name="value",
                        dataset_id=bundle.datasets[0].dataset_id,
                        selector="first",
                        column="missing",
                    ),
                ),
            ),
        ),
    )
    await agent.repair(
        draft=draft,
        errors=("0:GROUNDING_REJECTED:column is missing",),
        analysis_plan=analysis,
        bundle=bundle,
        visualization_previews=(),
        attempt=1,
        correlation_id="cor_agent_c_repair",
    )

    assert client.payload is not None
    assert client.payload["attempt"] == 1
    assert "immutable_dataset_bundle_hash" in client.payload
    assert "dataset_columns" in client.payload["allowed_ids"]
    assert '"rows"' not in json.dumps(client.payload, ensure_ascii=False)
