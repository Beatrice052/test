"""Programmatic candidate allowlists control Agent A output."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.agents.analyst_planner import DataAnalystPlannerAgent
from app.agents.base import AgentRuntime
from app.contracts.analysis import AnalyticalTask, PresentationPreference
from app.contracts.request import ChatRequest
from app.contracts.session import ActiveAnalyticalContext
from app.llm.rule_based import RuleBasedMockLLMClient
from app.orchestration.context import ContextTurnRouter
from app.orchestration.nodes import Phase2Nodes
from app.orchestration.planner_validation import (
    AnalysisPlanValidationError,
    AnalysisPlanValidator,
)
from app.persistence.database import Database
from app.persistence.session_repository import SessionRepository
from app.semantic.retriever import SemanticRetriever

ROOT = Path(__file__).parents[3]
PACKAGE = ROOT.parent / "compiled-semantic" / "mock"


@pytest.mark.asyncio
async def test_validator_promotes_allowlisted_draft_and_rejects_invented_field() -> None:
    database = Database("sqlite:///:memory:")
    database.create_schema()
    session = SessionRepository(database).create_session("subject-a")
    request = ChatRequest(
        session_id=session.object_id,
        message="查询2026年7月各Channel消息记录",
        client_turn_id="validator-turn-0001",
    )
    decision = ContextTurnRouter().decide(request, session)
    candidates = SemanticRetriever(PACKAGE).retrieve(request.message)
    draft = await DataAnalystPlannerAgent(
        AgentRuntime(llm=RuleBasedMockLLMClient(), system_prompt="strict")
    ).plan(
        request=request,
        active_context=ActiveAnalyticalContext(),
        turn_decision=decision,
        candidates=candidates,
        current_time=datetime(2026, 8, 1, tzinfo=UTC),
        correlation_id="cor_validator",
    )

    plan, route = AnalysisPlanValidator().validate(draft, candidates, decision)
    assert route == "resolve"
    assert plan.provenance.source_ids == (candidates.object_id, decision.object_id)

    presentation_only = plan.model_copy(
        update={
            "analysis_goal": "换成柱状图",
            "presentation_preference": PresentationPreference(
                requested_chart_type="bar", user_specified=True
            ),
        }
    )
    assert Phase2Nodes._data_signature(presentation_only) == Phase2Nodes._data_signature(plan)
    changed_scope = presentation_only.model_copy(
        update={
            "tasks": (
                presentation_only.tasks[0].model_copy(update={"dimension_ids": (), "grain": ()}),
            )
        }
    )
    assert Phase2Nodes._data_signature(changed_scope) != Phase2Nodes._data_signature(plan)

    invented_task = AnalyticalTask(
        task_id="task_invented",
        analytical_question="invented",
        analysis_type="summary",
        priority="required",
        metric_ids=plan.tasks[0].metric_ids,
        dimension_ids=("sub_message.nonexistent",),
        business_value="must fail",
    )
    invented = draft.model_copy(update={"tasks": (invented_task,)})
    with pytest.raises(AnalysisPlanValidationError) as error:
        AnalysisPlanValidator().validate(invented, candidates, decision)
    assert error.value.code == "CANDIDATE_ID_NOT_ALLOWED"
    database.dispose()
