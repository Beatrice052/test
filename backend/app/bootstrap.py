"""The single application composition root."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import aiosqlite
from alembic import command
from alembic.config import Config
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.agents.analyst_planner import DataAnalystPlannerAgent
from app.agents.base import AgentRuntime
from app.agents.insight_dashboard import InsightDashboardAgent
from app.agents.logical_query_planner import LogicalQueryPlannerAgent
from app.analytics.pipeline import AnalyticsPipeline
from app.contracts.analysis import AnalysisBudget
from app.gateway.base import OpenSearchGateway
from app.gateway.bindings import GatewayBindings
from app.gateway.executor import GatewayExecutor
from app.gateway.fixture_mock import FixtureBackedMockOpenSearchGateway
from app.gateway.mcp import McpOpenSearchGateway
from app.gateway.mcp_transport import McpConnectionConfig, OfficialMcpTransport
from app.llm.client import StructuredLLMClient
from app.llm.fixture import FixtureLLMClient
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.llm.recorded import RecordedLLMClient
from app.llm.rule_based import RuleBasedMockLLMClient
from app.observability.audit import AuditedLLMClient, SafeAuditLogger
from app.orchestration.graph import build_phase5_graph
from app.orchestration.nodes import Phase2Nodes
from app.orchestration.orchestrator import ChatBIOrchestrator
from app.orchestration.phase3_nodes import Phase3Nodes
from app.orchestration.phase4_nodes import Phase4Nodes
from app.orchestration.phase5_nodes import Phase5Nodes
from app.orchestration.planner_validation import AnalysisPlanValidator
from app.persistence.answer_repository import AnswerRepository
from app.persistence.database import Database, ensure_sqlite_parent
from app.persistence.idempotency_repository import IdempotencyRepository
from app.persistence.locks import SessionLockRepository
from app.persistence.session_repository import SessionRepository
from app.presentation.dashboard import ChartFeasibilityValidator, DashboardBuilder
from app.presentation.evidence import EvidenceBuilder
from app.presentation.exploration import GovernedVisualizationExplorer
from app.presentation.grounding import ClaimGrounder
from app.query.compiler import DslCompiler
from app.query.cost import QueryBudget
from app.query.finalizer import QueryPlanFinalizer
from app.query.index_router import IndexRouter
from app.query.validator import CompiledQueryValidator
from app.security.identity import (
    IdentityAdapter,
    StaticMockIdentityAdapter,
    TrustedHeaderIdentityAdapter,
)
from app.semantic.package import CompiledSemanticPackage
from app.semantic.resolver import AnalysisPlanResolver
from app.semantic.retriever import SemanticRetriever
from app.settings import AppSettings

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ANALYST_PROMPT = BACKEND_ROOT / "app" / "agents" / "prompts" / "analyst_planner.md"
QUERY_PLANNER_PROMPT = BACKEND_ROOT / "app" / "agents" / "prompts" / "logical_query_planner.md"
INSIGHT_PROMPT = BACKEND_ROOT / "app" / "agents" / "prompts" / "insight_dashboard.md"


@dataclass(slots=True)
class ApplicationContainer:
    settings: AppSettings
    database: Database
    semantic_package: CompiledSemanticPackage
    llm: StructuredLLMClient
    gateway: OpenSearchGateway
    orchestrator: ChatBIOrchestrator
    identity_adapter: IdentityAdapter
    checkpoint_connection: aiosqlite.Connection
    mcp_transport: OfficialMcpTransport | None = None

    async def readiness(self) -> dict[str, object]:
        if not self.database.schema_ready():
            return {"status": "not_ready", "reason": "database_migration"}
        if not self.settings.app_artifact_dir.is_dir() or not os.access(
            self.settings.app_artifact_dir, os.W_OK
        ):
            return {"status": "not_ready", "reason": "artifact_directory"}
        gateway_health = await self.gateway.health()
        if not gateway_health.ready:
            return {"status": "not_ready", "reason": "gateway_capabilities"}
        return {
            "status": "ready",
            "profile": "mock" if self.settings.is_mock_profile else self.settings.app_env,
            "llm_mode": self.settings.chatbi_llm_mode,
            "gateway_mode": self.settings.chatbi_gateway_mode,
        }

    async def close(self) -> None:
        if self.mcp_transport is not None:
            await self.mcp_transport.close()
        await self.checkpoint_connection.close()
        self.database.dispose()


async def build_container(settings: AppSettings) -> ApplicationContainer:
    """Build persistence, package, adapters, and the one StateGraph."""

    _run_migrations(settings.app_database_url)
    database = Database(settings.app_database_url)
    package = CompiledSemanticPackage(settings.chatbi_semantic_package_dir)
    settings.app_artifact_dir.mkdir(parents=True, exist_ok=True)
    settings.app_checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_connection = await aiosqlite.connect(settings.app_checkpoint_path)
    checkpointer = AsyncSqliteSaver(checkpoint_connection)
    await checkpointer.setup()
    audit = SafeAuditLogger()
    raw_llm = _build_llm(settings)
    maximum_analysis_budget = AnalysisBudget(
        max_queries=settings.chatbi_max_queries_per_turn,
        max_buckets=settings.chatbi_max_total_buckets,
        max_blocks=8,
    )
    llm = AuditedLLMClient(
        raw_llm,
        adapter_name=settings.chatbi_llm_mode,
        model_identifier=settings.chatbi_llm_model,
        audit=audit,
    )
    gateway, mcp_transport = await _build_gateway(settings)
    sessions = SessionRepository(database)
    answers = AnswerRepository(database)
    nodes = Phase2Nodes(
        sessions=sessions,
        answers=answers,
        retriever=SemanticRetriever(settings.chatbi_semantic_package_dir),
        planner=DataAnalystPlannerAgent(
            AgentRuntime(
                llm=llm,
                system_prompt=ANALYST_PROMPT.read_text(encoding="utf-8"),
                timeout_seconds=settings.chatbi_llm_timeout_seconds,
            ),
            visualization_definitions=package.visualizations(),
            maximum_budget=maximum_analysis_budget,
        ),
        validator=AnalysisPlanValidator(
            package.visualizations(), maximum_budget=maximum_analysis_budget
        ),
        resolver=AnalysisPlanResolver(package),
        semantic_package_version=package.manifest.package_version,
    )
    budget = QueryBudget(
        max_queries_per_turn=settings.chatbi_max_queries_per_turn,
        max_total_buckets=settings.chatbi_max_total_buckets,
        max_composite_pages=settings.chatbi_max_composite_pages,
        max_raw_response_bytes=settings.chatbi_max_raw_response_bytes,
        max_detail_hits=settings.chatbi_max_detail_hits,
        turn_timeout_seconds=settings.chatbi_turn_timeout_seconds,
    )
    phase3 = Phase3Nodes(
        sessions=sessions,
        planner=LogicalQueryPlannerAgent(
            AgentRuntime(
                llm=llm,
                system_prompt=QUERY_PLANNER_PROMPT.read_text(encoding="utf-8"),
                timeout_seconds=settings.chatbi_llm_timeout_seconds,
            )
        ),
        finalizer=QueryPlanFinalizer(
            index_router=IndexRouter(
                datasets=package.datasets(),
                policies=package.policies(),
                fields=package.fields(),
            ),
            budget=budget,
        ),
        compiler=DslCompiler(fields=package.fields(), metrics=package.metrics()),
        validator=CompiledQueryValidator(fields=package.fields(), policies=package.policies()),
        semantic_package_version=package.manifest.package_version,
    )
    phase4 = Phase4Nodes(
        sessions=sessions,
        executor=GatewayExecutor(
            gateway,
            mode=settings.chatbi_gateway_mode,
            max_attempts=2,
            audit=audit,
        ),
        compiler=DslCompiler(fields=package.fields(), metrics=package.metrics()),
        validator=CompiledQueryValidator(fields=package.fields(), policies=package.policies()),
        analytics=AnalyticsPipeline(
            metric_definitions=package.metrics(),
            value_dictionaries=package.values(),
            method_definitions=package.methods(),
            fields=package.fields(),
        ),
        semantic_package_version=package.manifest.package_version,
        max_composite_pages=settings.chatbi_max_composite_pages,
        max_raw_response_bytes=settings.chatbi_max_raw_response_bytes,
    )
    chart_validator = ChartFeasibilityValidator(package.visualizations())
    phase5 = Phase5Nodes(
        sessions=sessions,
        answers=answers,
        agent=InsightDashboardAgent(
            AgentRuntime(
                llm=llm,
                system_prompt=INSIGHT_PROMPT.read_text(encoding="utf-8"),
                timeout_seconds=settings.chatbi_llm_timeout_seconds,
            )
        ),
        grounder=ClaimGrounder(),
        dashboard_builder=DashboardBuilder(package.metrics()),
        visualization_explorer=GovernedVisualizationExplorer(chart_validator),
        evidence_builder=EvidenceBuilder(),
        metric_definitions=package.metrics(),
        method_definitions=package.methods(),
        visualization_definitions=package.visualizations(),
        semantic_package_version=package.manifest.package_version,
    )
    graph = build_phase5_graph(nodes, phase3, phase4, phase5, checkpointer=checkpointer)
    orchestrator = ChatBIOrchestrator(
        graph=graph,
        sessions=sessions,
        answers=answers,
        idempotency=IdempotencyRepository(database),
        locks=SessionLockRepository(database),
        lock_lease_seconds=max(120, settings.chatbi_turn_timeout_seconds + 30),
        turn_timeout_seconds=settings.chatbi_turn_timeout_seconds,
        audit=audit,
    )
    return ApplicationContainer(
        settings=settings,
        database=database,
        semantic_package=package,
        llm=raw_llm,
        gateway=gateway,
        orchestrator=orchestrator,
        identity_adapter=(
            StaticMockIdentityAdapter()
            if settings.use_mock_identity
            else TrustedHeaderIdentityAdapter()
        ),
        checkpoint_connection=checkpoint_connection,
        mcp_transport=mcp_transport,
    )


def _run_migrations(database_url: str) -> None:
    ensure_sqlite_parent(database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def _build_llm(settings: AppSettings) -> StructuredLLMClient:
    if settings.chatbi_llm_mode == "fixture":
        return FixtureLLMClient.from_file(settings.chatbi_llm_fixture_path)
    if settings.chatbi_llm_mode == "rule_based":
        return RuleBasedMockLLMClient()
    if settings.chatbi_llm_mode == "recorded":
        return RecordedLLMClient.from_file(settings.chatbi_llm_recording_path)
    if settings.chatbi_llm_mode == "openai_compatible":
        if settings.chatbi_llm_base_url is None or settings.chatbi_llm_model is None:
            raise ValueError(
                "openai_compatible LLM requires CHATBI_LLM_BASE_URL and CHATBI_LLM_MODEL"
            )
        return OpenAICompatibleLLMClient(
            base_url=settings.chatbi_llm_base_url,
            model=settings.chatbi_llm_model,
            api_key=settings.chatbi_llm_api_key,
        )
    raise ValueError(f"unknown LLM adapter mode: {settings.chatbi_llm_mode}")


async def _build_gateway(
    settings: AppSettings,
) -> tuple[OpenSearchGateway, OfficialMcpTransport | None]:
    if settings.chatbi_gateway_mode == "mock":
        return FixtureBackedMockOpenSearchGateway(settings.chatbi_gateway_fixture_path), None
    if settings.chatbi_gateway_mode == "mcp":
        transport = OfficialMcpTransport(
            McpConnectionConfig(
                transport=settings.opensearch_mcp_transport,
                endpoint=settings.opensearch_mcp_endpoint,
                command=settings.opensearch_mcp_command,
                args=settings.opensearch_mcp_args_json,
                call_timeout_seconds=settings.opensearch_mcp_call_timeout_seconds,
            )
        )
        await transport.connect()
        gateway = McpOpenSearchGateway(
            transport=transport,
            bindings=GatewayBindings.from_file(settings.chatbi_gateway_config_path),
            max_raw_response_bytes=settings.chatbi_max_raw_response_bytes,
        )
        await gateway.probe()
        return gateway, transport
    raise ValueError("direct Gateway requires a separately approved adapter")
