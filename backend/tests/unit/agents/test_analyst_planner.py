"""Agent A sees minimal candidates and can only produce a strict draft."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.agents.analyst_planner import DataAnalystPlannerAgent
from app.agents.base import AgentRuntime
from app.contracts.analysis import AnalysisPlanDraft
from app.contracts.dashboard import VisualizationDefinition
from app.contracts.request import ChatRequest
from app.contracts.session import ActiveAnalyticalContext
from app.llm.rule_based import RuleBasedMockLLMClient
from app.orchestration.context import ContextTurnRouter
from app.persistence.database import Database
from app.persistence.session_repository import SessionRepository
from app.semantic.retriever import SemanticRetriever

ROOT = Path(__file__).parents[3]
PACKAGE = ROOT.parent / "compiled-semantic" / "mock"
PROMPT = ROOT / "app" / "agents" / "prompts" / "analyst_planner.md"


class CaptureAnalystClient:
    def __init__(self) -> None:
        self.delegate = RuleBasedMockLLMClient()
        self.payload: dict[str, object] | None = None

    async def generate(self, **kwargs: Any) -> AnalysisPlanDraft:
        self.payload = kwargs["input_payload"]
        return await self.delegate.generate(**kwargs)


@pytest.mark.asyncio
async def test_rule_based_agent_references_only_retrieved_candidate_ids() -> None:
    database = Database("sqlite:///:memory:")
    database.create_schema()
    session = SessionRepository(database).create_session("subject-a")
    request = ChatRequest(
        session_id=session.object_id,
        message="查询2026年7月各Channel失败率",
        client_turn_id="agent-turn-0001",
    )
    decision = ContextTurnRouter().decide(request, session)
    candidates = SemanticRetriever(PACKAGE).retrieve(request.message)
    client = RuleBasedMockLLMClient()
    agent = DataAnalystPlannerAgent(
        AgentRuntime(llm=client, system_prompt=PROMPT.read_text(encoding="utf-8"))
    )

    draft = await agent.plan(
        request=request,
        active_context=ActiveAnalyticalContext(),
        turn_decision=decision,
        candidates=candidates,
        current_time=datetime(2026, 8, 1, tzinfo=UTC),
        correlation_id="cor_agent",
    )

    allowed = {
        item.item_id
        for items in (
            candidates.dataset_candidates,
            candidates.metric_candidates,
            candidates.field_candidates,
        )
        for item in items
    }
    referenced = {
        *draft.scope.dataset_ids,
        *(item.metric_id for item in draft.metric_decisions),
        *(field_id for task in draft.tasks for field_id in task.dimension_ids),
    }
    assert referenced <= allowed
    assert "failure_rate.v1" in referenced
    assert client.calls == ["turn_and_analysis_plan"]
    assert "不要生成 DSL" in PROMPT.read_text(encoding="utf-8")
    database.dispose()


def test_analysis_plan_draft_is_closed_and_contains_no_tool_surface() -> None:
    schema = AnalysisPlanDraft.model_json_schema()
    serialized = str(schema).lower()
    assert "additionalproperties': false" in serialized
    assert "tool" not in serialized
    assert "query_dsl" not in serialized


@pytest.mark.asyncio
async def test_agent_a_receives_the_deployed_visualization_catalog_not_a_fixed_bundle() -> None:
    database = Database("sqlite:///:memory:")
    database.create_schema()
    session = SessionRepository(database).create_session("subject-catalog")
    request = ChatRequest(
        session_id=session.object_id,
        message="展示消息变化",
        client_turn_id="agent-turn-catalog",
    )
    client = CaptureAnalystClient()
    definition = VisualizationDefinition(
        visualization_id="governed_time_view",
        version="v1",
        intent="time_view",
        allowed_chart_types=("line",),
        minimum_time_points=2,
    )
    agent = DataAnalystPlannerAgent(
        AgentRuntime(llm=client, system_prompt="strict"),
        visualization_definitions=(definition,),
    )
    await agent.plan(
        request=request,
        active_context=ActiveAnalyticalContext(),
        turn_decision=ContextTurnRouter().decide(request, session),
        candidates=SemanticRetriever(PACKAGE).retrieve(request.message),
        current_time=datetime(2026, 8, 1, tzinfo=UTC),
        correlation_id="cor_catalog",
    )

    assert client.payload is not None
    catalog = client.payload["presentation_catalog"]
    assert isinstance(catalog, dict)
    assert catalog["allowed_chart_types"] == ["line", "table", "pivot"]
    assert catalog["visualization_intents"] == [
        {
            "intent": "time_view",
            "allowed_chart_types": ["line"],
            "minimum_rows": 1,
            "maximum_categories": 20,
            "minimum_time_points": 2,
            "requires_complete_distribution": False,
        }
    ]
    database.dispose()
