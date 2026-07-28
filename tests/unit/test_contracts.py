from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.contracts import AnalysisPlan, QueryPlan
from app.agent.state import AgentState, RunStatus
from app.api.schemas import ChatRequest, ChatResponse, ChatStatus


def _analysis_payload() -> dict:
    return {
        "analysis_type": "metric_breakdown",
        "dataset_concept": "sub_message",
        "metric_concepts": ["failure_rate"],
        "dimension_concepts": ["channel"],
        "time_range": {
            "type": "absolute",
            "from": "2026-07-01T00:00:00+08:00",
            "to": "2026-08-01T00:00:00+08:00",
        },
        "requested_outputs": ["kpi", "table", "chart", "summary"],
    }


def test_analysis_plan_serializes_with_aliases() -> None:
    plan = AnalysisPlan.model_validate(_analysis_payload())

    result = plan.model_dump(mode="json", by_alias=True)

    assert result["time_range"]["from"] == "2026-07-01T00:00:00+08:00"
    assert "tool" not in result
    assert "dsl" not in result


@pytest.mark.parametrize("forbidden_key", ["tool", "mcp_tool", "query_dsl", "dsl"])
def test_analysis_plan_rejects_execution_fields(forbidden_key: str) -> None:
    payload = _analysis_payload()
    payload[forbidden_key] = "SearchIndexTool"

    with pytest.raises(ValidationError):
        AnalysisPlan.model_validate(payload)


def test_analysis_plan_rejects_non_half_open_range() -> None:
    payload = _analysis_payload()
    payload["time_range"]["to"] = payload["time_range"]["from"]

    with pytest.raises(ValidationError, match="from < to"):
        AnalysisPlan.model_validate(payload)


@pytest.mark.parametrize("forbidden_key", ["tool", "mcp_tool", "query_dsl", "dsl"])
def test_query_plan_rejects_tool_and_dsl(forbidden_key: str) -> None:
    payload = {
        "query_id": "q-001",
        "dataset_id": "sub_message",
        "physical_indices": ["tbl_os_sub_message_2026_07"],
        "query_type": "count",
        "time_filter": {},
        forbidden_key: {},
    }

    with pytest.raises(ValidationError):
        QueryPlan.model_validate(payload)


def test_agent_state_allows_only_declared_transitions() -> None:
    state = AgentState(
        run_id="run-001",
        session_id="session-001",
        user_question="count records",
    )

    planned = state.transition(RunStatus.PLANNED)

    assert state.status == RunStatus.RECEIVED
    assert planned.status == RunStatus.PLANNED
    with pytest.raises(ValueError, match="invalid state transition"):
        planned.transition(RunStatus.EXECUTED)


def test_terminal_agent_state_cannot_transition() -> None:
    state = AgentState(
        run_id="run-001",
        session_id="session-001",
        user_question="blocked request",
        status=RunStatus.POLICY_BLOCKED,
    )

    with pytest.raises(ValueError, match="terminal state"):
        state.transition(RunStatus.PRESENTED)


def test_chat_contract_strips_message_and_has_stable_empty_components() -> None:
    request = ChatRequest(session_id="session-001", message="  hello  ")
    response = ChatResponse(
        session_id=request.session_id or "generated",
        status=ChatStatus.NOT_ANSWERABLE,
        assistant_message="Not available yet",
    )

    assert request.message == "hello"
    assert response.kpis == []
    assert response.table is None
    assert response.chart is None
    assert response.model_dump(mode="json")["status"] == "not_answerable"


def test_chat_request_rejects_blank_or_unsafe_session_id() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(session_id="session/../../secret", message="hello")
    with pytest.raises(ValidationError):
        ChatRequest(session_id="session-001", message="   ")
