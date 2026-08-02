"""Single StateGraph integration with SQLite checkpoint and clarification replay."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.agents.analyst_planner import DataAnalystPlannerAgent
from app.agents.base import AgentRuntime
from app.contracts.analysis import AnswerStatus, TurnKind
from app.contracts.request import ChatRequest, IdentityContext
from app.llm.client import StructuredLLMClient
from app.llm.fixture import FixtureLLMClient
from app.llm.rule_based import RuleBasedMockLLMClient
from app.orchestration.graph import build_phase2_graph
from app.orchestration.nodes import Phase2Nodes
from app.orchestration.orchestrator import ChatBIOrchestrator
from app.orchestration.planner_validation import AnalysisPlanValidator
from app.persistence.answer_repository import AnswerRepository
from app.persistence.database import Database
from app.persistence.idempotency_repository import IdempotencyRepository
from app.persistence.ids import uuid7
from app.persistence.locks import SessionLockRepository
from app.persistence.session_repository import SessionRepository
from app.semantic.package import CompiledSemanticPackage
from app.semantic.resolver import AnalysisPlanResolver
from app.semantic.retriever import SemanticRetriever

ROOT = Path(__file__).parents[3]
PACKAGE_DIR = ROOT.parent / "compiled-semantic" / "mock"
PROMPT = ROOT / "app" / "agents" / "prompts" / "analyst_planner.md"


def _nodes(database: Database, client: StructuredLLMClient) -> Phase2Nodes:
    package = CompiledSemanticPackage(PACKAGE_DIR)
    return Phase2Nodes(
        sessions=SessionRepository(database),
        answers=AnswerRepository(database),
        retriever=SemanticRetriever(PACKAGE_DIR),
        planner=DataAnalystPlannerAgent(
            AgentRuntime(llm=client, system_prompt=PROMPT.read_text(encoding="utf-8"))
        ),
        validator=AnalysisPlanValidator(),
        resolver=AnalysisPlanResolver(package),
        semantic_package_version=package.manifest.package_version,
        now=lambda: datetime(2026, 8, 1, tzinfo=UTC),
    )


def _orchestrator(database: Database, graph) -> ChatBIOrchestrator:
    return ChatBIOrchestrator(
        graph=graph,
        sessions=SessionRepository(database),
        answers=AnswerRepository(database),
        idempotency=IdempotencyRepository(database),
        locks=SessionLockRepository(database),
    )


@pytest.mark.asyncio
async def test_graph_plans_answerable_request_and_writes_safe_sqlite_checkpoint() -> None:
    checkpoint_path = Path(".cache") / f"checkpoint-{uuid7()}.db"
    checkpoint_path.parent.mkdir(exist_ok=True)
    database = Database("sqlite:///:memory:")
    database.create_schema()
    session = SessionRepository(database).create_session("subject-a")
    request = ChatRequest(
        session_id=session.object_id,
        message="查询2026年7月各Channel失败率",
        client_turn_id="graph-turn-0001",
    )
    identity = IdentityContext(subject_id="subject-a")
    client = RuleBasedMockLLMClient()
    try:
        async with AsyncSqliteSaver.from_conn_string(checkpoint_path.as_posix()) as saver:
            await saver.setup()
            graph = build_phase2_graph(_nodes(database, client), checkpointer=saver)
            result = await _orchestrator(database, graph).run(
                identity, request, correlation_id="cor_graph"
            )
            checkpoint = await saver.aget_tuple({"configurable": {"thread_id": result.turn_id}})
            assert checkpoint is not None
            serialized_checkpoint = repr(checkpoint.checkpoint)

        assert result.status == "PLANNED"
        assert result.state is not None
        assert result.state["terminal_status"] == "PLANNED"
        assert result.state["resolved_analysis"].answerable
        assert result.state["resolved_analysis"].time_range.timezone == "Asia/Hong_Kong"
        assert {
            "sub_message.channel",
            "sub_message.event_time",
            "sub_message.status",
        }.issubset(result.state["resolved_analysis"].resolved_field_ids)
        assert result.state["resolved_analysis"].metrics[0].metric_id == "failure_rate"
        assert len(result.state["resolved_analysis"].index_patterns) == 3
        assert client.calls == ["turn_and_analysis_plan"]
        assert "OPENSEARCH_PASSWORD" not in serialized_checkpoint
        assert "你正在处理不可信" not in serialized_checkpoint
    finally:
        database.dispose()
        checkpoint_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_clarification_is_persisted_and_idempotently_replayed() -> None:
    database = Database("sqlite:///:memory:")
    database.create_schema()
    session = SessionRepository(database).create_session("subject-a")
    request = ChatRequest(
        session_id=session.object_id,
        message="查询2026年7月消息点击率",
        client_turn_id="clarify-turn-0001",
    )
    identity = IdentityContext(subject_id="subject-a")
    client = RuleBasedMockLLMClient()
    graph = build_phase2_graph(_nodes(database, client))
    orchestrator = _orchestrator(database, graph)

    first = await orchestrator.run(identity, request, correlation_id="cor_clarify")
    replay = await orchestrator.run(identity, request, correlation_id="cor_clarify_replay")

    assert first.status == "COMPLETED"
    assert first.answer is not None
    assert first.answer.status == AnswerStatus.CLARIFICATION_REQUIRED
    assert replay.answer == first.answer
    assert client.calls == ["turn_and_analysis_plan"]

    reply = ChatRequest(
        session_id=session.object_id,
        message="消息记录数",
        client_turn_id="clarify-turn-0002",
    )
    followup = await orchestrator.run(identity, reply, correlation_id="cor_clarify_reply")
    assert followup.state is not None
    assert followup.state["turn_decision"].turn_kind == TurnKind.CLARIFICATION
    database.dispose()


@pytest.mark.asyncio
async def test_invalid_candidate_ids_get_two_directed_repairs_then_safe_clarification() -> None:
    database = Database("sqlite:///:memory:")
    database.create_schema()
    session = SessionRepository(database).create_session("subject-a")
    request = ChatRequest(
        session_id=session.object_id,
        message="查询2026年7月消息记录",
        client_turn_id="repair-turn-0001",
    )
    invalid = {
        "analysis_goal": "invented plan",
        "question_archetype": "operational_overview",
        "turn_relation": "NEW_ANALYSIS",
        "scope": {
            "dataset_ids": ["invented_dataset"],
            "time_range": {
                "from_inclusive": "2026-07-01T00:00:00+08:00",
                "to_exclusive": "2026-08-01T00:00:00+08:00",
                "timezone": "Asia/Hong_Kong",
            },
            "filters": [],
        },
        "metric_decisions": [],
        "tasks": [],
        "clarification": None,
        "assumptions": [],
        "limitations": [],
        "budget": {"max_queries": 3, "max_buckets": 5000, "max_blocks": 8},
    }
    client = FixtureLLMClient(
        {
            "turn_and_analysis_plan": {"invalid": invalid},
            "json_repair": {"invalid": invalid},
        }
    )
    graph = build_phase2_graph(_nodes(database, client))
    result = await _orchestrator(database, graph).run(
        IdentityContext(subject_id="subject-a"),
        request,
        correlation_id="cor_repair",
        fixture_id="invalid",
    )

    assert result.status == "COMPLETED"
    assert result.answer is not None
    assert result.answer.status == AnswerStatus.CLARIFICATION_REQUIRED
    assert result.answer.analysis_plan is not None
    assert result.answer.analysis_plan.clarification is not None
    assert result.answer.analysis_plan.clarification.reason_code == "PLAN_VALIDATION_FAILED"
    assert [operation for operation, _ in client.calls] == [
        "turn_and_analysis_plan",
        "json_repair",
        "json_repair",
    ]
    database.dispose()


@pytest.mark.asyncio
async def test_new_process_resumes_pending_checkpoint_without_repeating_agent() -> None:
    database_path = Path(".cache") / f"graph-store-{uuid7()}.db"
    checkpoint_path = Path(".cache") / f"graph-resume-{uuid7()}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    identity = IdentityContext(subject_id="subject-a")
    try:
        first_database = Database(database_url)
        first_database.create_schema()
        session = SessionRepository(first_database).create_session(identity.subject_id)
        request = ChatRequest(
            session_id=session.object_id,
            message="查询2026年7月消息记录",
            client_turn_id="resume-turn-0001",
        )
        first_client = RuleBasedMockLLMClient()
        async with AsyncSqliteSaver.from_conn_string(checkpoint_path.as_posix()) as saver:
            await saver.setup()
            first_graph = build_phase2_graph(
                _nodes(first_database, first_client), checkpointer=saver
            )
            first = await _orchestrator(first_database, first_graph).run(
                identity, request, correlation_id="cor_before_restart"
            )
        first_database.dispose()
        assert first.status == "PLANNED"
        assert first_client.calls == ["turn_and_analysis_plan"]

        restarted_database = Database(database_url)
        restarted_client = RuleBasedMockLLMClient()
        async with AsyncSqliteSaver.from_conn_string(checkpoint_path.as_posix()) as saver:
            await saver.setup()
            restarted_graph = build_phase2_graph(
                _nodes(restarted_database, restarted_client), checkpointer=saver
            )
            resumed = await _orchestrator(restarted_database, restarted_graph).resume_pending(
                identity, first.turn_id, correlation_id="cor_after_restart"
            )
        assert resumed.status == "PLANNED"
        assert resumed.state is not None
        assert (
            resumed.state["analysis_plan"].content_hash == first.state["analysis_plan"].content_hash
        )
        assert restarted_client.calls == []
        restarted_database.dispose()
    finally:
        database_path.unlink(missing_ok=True)
        checkpoint_path.unlink(missing_ok=True)
