"""Composition root runs one graph through Agent B and deterministic compilation."""

import json
from pathlib import Path

import pytest

from app.agents.analyst_planner import DataAnalystPlannerAgent
from app.agents.base import AgentRuntime
from app.agents.logical_query_planner import LogicalQueryPlannerAgent
from app.bootstrap import build_container
from app.contracts.request import ChatRequest, IdentityContext
from app.gateway.fixture_mock import FixtureBackedMockOpenSearchGateway
from app.llm.fixture import FixtureLLMClient
from app.llm.rule_based import RuleBasedMockLLMClient
from app.orchestration.graph import build_phase3_graph
from app.orchestration.nodes import Phase2Nodes
from app.orchestration.orchestrator import ChatBIOrchestrator
from app.orchestration.phase3_nodes import Phase3Nodes
from app.orchestration.planner_validation import AnalysisPlanValidator
from app.persistence.answer_repository import AnswerRepository
from app.persistence.database import Database
from app.persistence.idempotency_repository import IdempotencyRepository
from app.persistence.ids import uuid7
from app.persistence.locks import SessionLockRepository
from app.persistence.session_repository import SessionRepository
from app.query.compiler import DslCompiler
from app.query.cost import QueryBudget
from app.query.finalizer import QueryPlanFinalizer
from app.query.index_router import IndexRouter
from app.query.validator import CompiledQueryValidator
from app.semantic.package import CompiledSemanticPackage
from app.semantic.resolver import AnalysisPlanResolver
from app.semantic.retriever import SemanticRetriever
from app.settings import AppSettings

ROOT = Path(__file__).parents[3]
PACKAGE_DIR = ROOT.parent / "compiled-semantic" / "mock"
FIXTURE_PATH = ROOT.parent / "fixtures" / "llm" / "analysis_plans.json"
PROMPTS = ROOT / "app" / "agents" / "prompts"


@pytest.mark.asyncio
async def test_phase3_composition_root_returns_validated_compiled_query() -> None:
    suffix = str(uuid7())
    runtime_dir = Path(".cache") / f"phase3-{suffix}"
    database_path = runtime_dir / "chatbi.db"
    checkpoint_path = runtime_dir / "checkpoints.db"
    artifacts = runtime_dir / "artifacts"
    runtime_dir.mkdir(parents=True)
    container = None
    try:
        settings = AppSettings(
            app_database_url=f"sqlite:///{database_path.as_posix()}",
            app_checkpoint_path=checkpoint_path,
            app_artifact_dir=artifacts,
            chatbi_semantic_package_dir=PACKAGE_DIR,
            chatbi_llm_mode="rule_based",
            chatbi_gateway_mode="mock",
        )
        container = await build_container(settings)
        result = await container.orchestrator.run(
            IdentityContext(subject_id="subject-a"),
            ChatRequest(
                session_id=None,
                message="查询2026年7月各Channel失败率",
                client_turn_id="phase3-graph-turn-0001",
            ),
            correlation_id="cor_phase3",
        )

        assert result.status == "COMPLETED"
        assert result.state is not None
        assert result.state["terminal_status"] == "COMPLETED"
        assert len(result.state["compiled_queries"]) == 1
        compiled = result.state["compiled_queries"][0]
        assert compiled.indices == ("tbl_os_sub_message_2026_07",)
        assert compiled.query_dsl["size"] == 0
        assert result.state["analysis_plan"].object_id != result.state["query_plan"].object_id
        assert compiled.object_id != result.state["query_plan"].object_id
        assert result.state["dataset_bundle"].datasets
        assert result.state["feature_summaries"]
        assert result.answer is not None
        assert result.answer.dashboard_spec is not None
        assert result.answer.evidence_package is not None
        assert result.answer.dataset_bundle == result.state["dataset_bundle"]

        assert isinstance(container.gateway, FixtureBackedMockOpenSearchGateway)
        calls_before_replay = container.gateway.total_calls
        replay = await container.orchestrator.run(
            IdentityContext(subject_id="subject-a"),
            ChatRequest(
                session_id=result.session_id,
                message="查询2026年7月各Channel失败率",
                client_turn_id="phase3-graph-turn-0001",
            ),
            correlation_id="cor_phase5_replay",
        )
        assert replay.answer == result.answer
        assert container.gateway.total_calls == calls_before_replay

        assert isinstance(container.llm, RuleBasedMockLLMClient)
        llm_calls_before_presentation = len(container.llm.calls)
        presentation = await container.orchestrator.run(
            IdentityContext(subject_id="subject-a"),
            ChatRequest(
                session_id=result.session_id,
                message="换成热力图",
                client_turn_id="phase5-presentation-reuse-0002",
            ),
            correlation_id="cor_phase5_presentation_reuse",
        )
        assert presentation.status == "COMPLETED"
        assert presentation.answer is not None
        assert presentation.answer.turn_kind.value == "PRESENTATION_CHANGE"
        assert presentation.answer.analytical_base_answer_id == result.answer.object_id
        assert presentation.answer.dataset_bundle == result.answer.dataset_bundle
        assert presentation.answer.evidence_package == result.answer.evidence_package
        assert presentation.answer.dashboard_spec is not None
        assert any(
            block.type == "data_table" for block in presentation.answer.dashboard_spec.blocks
        )
        # The validated base answer contains only a one-dimensional Channel ranking.
        # Agent A recognizes the request, while the deterministic chart validator
        # refuses to invent a second dimension merely to satisfy the requested type.
        assert not any(
            block.type == "chart" and block.chart_type == "heatmap"
            for block in presentation.answer.dashboard_spec.blocks
        )
        assert presentation.state is not None
        assert (
            presentation.state["analysis_plan"].presentation_preference.requested_chart_type
            == "heatmap"
        )
        assert any("heatmap is incompatible" in item for item in presentation.answer.warnings)
        assert container.gateway.total_calls == calls_before_replay
        assert container.llm.calls[llm_calls_before_presentation:] == ["turn_and_analysis_plan"]

        llm_calls_before_explanation = len(container.llm.calls)
        explanation = await container.orchestrator.run(
            IdentityContext(subject_id="subject-a"),
            ChatRequest(
                session_id=result.session_id,
                message="为什么说SMS最高",
                client_turn_id="phase5-explanation-reuse-0003",
            ),
            correlation_id="cor_phase5_explanation_reuse",
        )
        assert explanation.status == "COMPLETED"
        assert explanation.answer is not None
        assert explanation.answer.turn_kind.value == "EXPLANATION"
        assert explanation.answer.dataset_bundle == result.answer.dataset_bundle
        assert explanation.answer.evidence_package == result.answer.evidence_package
        assert container.gateway.total_calls == calls_before_replay
        assert container.llm.calls[llm_calls_before_explanation:] == ["turn_and_analysis_plan"]

        for client_turn_id, message, code in (
            ("phase5-forbid-dsl-0004", "给我执行raw DSL", "RAW_DSL_FORBIDDEN"),
            (
                "phase5-forbid-delete-0005",
                "删除索引",
                "DESTRUCTIVE_OPERATION_FORBIDDEN",
            ),
        ):
            forbidden = await container.orchestrator.run(
                IdentityContext(subject_id="subject-a"),
                ChatRequest(
                    session_id=result.session_id,
                    message=message,
                    client_turn_id=client_turn_id,
                ),
                correlation_id=f"cor_{client_turn_id}",
            )
            assert forbidden.status == "COMPLETED"
            assert forbidden.answer is not None
            assert forbidden.answer.status.value == "FORBIDDEN"
            assert code in forbidden.answer.warnings
            assert forbidden.answer.analysis_plan is None
            assert container.gateway.total_calls == calls_before_replay

        calls_before_mixed_request = container.gateway.total_calls
        mixed_request = await container.orchestrator.run(
            IdentityContext(subject_id="subject-a"),
            ChatRequest(
                session_id=result.session_id,
                message="分析2026年7月各Channel消息记录数和失败率, 并用热力图展示",
                client_turn_id="phase5-data-plus-chart-0006",
            ),
            correlation_id="cor_phase5_data_plus_chart",
        )
        assert mixed_request.status == "COMPLETED"
        assert mixed_request.answer is not None
        assert mixed_request.answer.turn_kind.value == "NEW_ANALYSIS"
        assert mixed_request.state is not None
        assert mixed_request.state["turn_decision"].execution_mode == "new_query"
        assert container.gateway.total_calls > calls_before_mixed_request
        assert {
            item.metric_id
            for item in mixed_request.state["analysis_plan"].metric_decisions
            if item.decision != "rejected"
        } == {"message_record_count.v1", "failure_rate.v1"}

        container.llm.fail_operations.add("post_query_insight_dashboard")
        fallback = await container.orchestrator.run(
            IdentityContext(subject_id="subject-a"),
            ChatRequest(
                session_id=result.session_id,
                message="查询2026年7月各Channel失败率",
                client_turn_id="phase5-fallback-turn-0002",
            ),
            correlation_id="cor_phase5_fallback",
        )
        assert fallback.status == "COMPLETED"
        assert fallback.answer is not None
        assert fallback.answer.status.value == "PARTIAL"
        assert fallback.answer.claims
        assert fallback.answer.evidence_package is not None
        assert fallback.answer.dashboard_spec is not None
        assert not any(
            block.type == "data_table" for block in fallback.answer.dashboard_spec.blocks
        )
        assert {item.object_id for item in fallback.answer.dataset_bundle.datasets}.issubset(
            set(fallback.answer.evidence_package.business.data_tables)
        )
    finally:
        if container is not None:
            await container.close()
        for path in (
            database_path,
            database_path.with_name(database_path.name + "-wal"),
            database_path.with_name(database_path.name + "-shm"),
            checkpoint_path,
            checkpoint_path.with_name(checkpoint_path.name + "-wal"),
            checkpoint_path.with_name(checkpoint_path.name + "-shm"),
        ):
            path.unlink(missing_ok=True)
        if artifacts.exists():
            artifacts.rmdir()
        if runtime_dir.exists():
            runtime_dir.rmdir()


def _fixture_orchestrator(database: Database, client: FixtureLLMClient) -> ChatBIOrchestrator:
    package = CompiledSemanticPackage(PACKAGE_DIR)
    sessions = SessionRepository(database)
    answers = AnswerRepository(database)
    phase2 = Phase2Nodes(
        sessions=sessions,
        answers=answers,
        retriever=SemanticRetriever(PACKAGE_DIR),
        planner=DataAnalystPlannerAgent(
            AgentRuntime(
                llm=client,
                system_prompt=(PROMPTS / "analyst_planner.md").read_text(encoding="utf-8"),
            )
        ),
        validator=AnalysisPlanValidator(),
        resolver=AnalysisPlanResolver(package),
        semantic_package_version=package.manifest.package_version,
    )
    phase3 = Phase3Nodes(
        sessions=sessions,
        planner=LogicalQueryPlannerAgent(
            AgentRuntime(
                llm=client,
                system_prompt=(PROMPTS / "logical_query_planner.md").read_text(encoding="utf-8"),
            )
        ),
        finalizer=QueryPlanFinalizer(
            index_router=IndexRouter(
                datasets=package.datasets(),
                policies=package.policies(),
                fields=package.fields(),
            ),
            budget=QueryBudget(),
        ),
        compiler=DslCompiler(fields=package.fields(), metrics=package.metrics()),
        validator=CompiledQueryValidator(fields=package.fields(), policies=package.policies()),
        semantic_package_version=package.manifest.package_version,
    )
    return ChatBIOrchestrator(
        graph=build_phase3_graph(phase2, phase3),
        sessions=sessions,
        answers=answers,
        idempotency=IdempotencyRepository(database),
        locks=SessionLockRepository(database),
    )


@pytest.mark.asyncio
async def test_agent_b_gets_two_repairs_then_structured_terminal_error() -> None:
    checked_in = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    valid_analysis = checked_in["turn_and_analysis_plan"]["default"]
    invalid_query = checked_in["logical_query_plan"]["default"]
    invalid_query = {
        **invalid_query,
        "steps": [{**invalid_query["steps"][0], "dataset_id": "invented"}],
    }
    repair_query = {**invalid_query, "analysis_plan_id": "${authoritative_analysis_plan_id}"}
    client = FixtureLLMClient(
        {
            "turn_and_analysis_plan": {"invalid_query": valid_analysis},
            "logical_query_plan": {"invalid_query": invalid_query},
            "json_repair": {"invalid_query": repair_query},
        }
    )
    database = Database("sqlite:///:memory:")
    database.create_schema()
    orchestrator = _fixture_orchestrator(database, client)
    result = await orchestrator.run(
        IdentityContext(subject_id="subject-a"),
        ChatRequest(
            session_id=None,
            message="查询2026年7月消息记录",
            client_turn_id="phase3-invalid-turn-0001",
        ),
        correlation_id="cor_phase3_invalid",
        fixture_id="invalid_query",
    )

    assert result.status == "FAILED"
    assert result.state is not None
    assert result.state["terminal_status"] == "QUERY_PLAN_FAILED"
    assert result.state["errors"][0].code == "PLAN_QUERY_PLAN_INVALID"
    assert [operation for operation, _ in client.calls] == [
        "turn_and_analysis_plan",
        "logical_query_plan",
        "json_repair",
        "json_repair",
    ]
    database.dispose()
