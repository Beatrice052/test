"""AnalysisPlan -> ResolvedAnalysis -> QueryPlan -> CompiledQuery stays layered."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.agents.analyst_planner import DataAnalystPlannerAgent
from app.agents.base import AgentRuntime
from app.agents.logical_query_planner import LogicalQueryPlannerAgent
from app.contracts.execution import RawSearchResult, ShardSummary
from app.contracts.query import ParameterBinding
from app.contracts.request import ChatRequest
from app.gateway.mock import MockOpenSearchGateway
from app.llm.rule_based import RuleBasedMockLLMClient
from app.orchestration.context import ContextTurnRouter
from app.orchestration.planner_validation import AnalysisPlanValidator
from app.persistence.database import Database
from app.persistence.session_repository import SessionRepository
from app.query.builder import DependentQueryBinder
from app.query.compiler import DslCompiler
from app.query.cost import QueryBudget
from app.query.finalizer import QueryPlanFinalizationError, QueryPlanFinalizer
from app.query.index_router import IndexRouter
from app.query.validator import CompiledQueryValidator, QueryValidationError
from app.semantic.package import CompiledSemanticPackage
from app.semantic.resolver import AnalysisPlanResolver
from app.semantic.retriever import SemanticRetriever

ROOT = Path(__file__).parents[3]
PACKAGE_DIR = ROOT.parent / "compiled-semantic" / "mock"
PROMPTS = ROOT / "app" / "agents" / "prompts"


async def _plans(message: str):
    package = CompiledSemanticPackage(PACKAGE_DIR)
    database = Database("sqlite:///:memory:")
    database.create_schema()
    session = SessionRepository(database).create_session("subject-a")
    request = ChatRequest(
        session_id=session.object_id,
        message=message,
        client_turn_id="query-plan-turn-0001",
    )
    decision = ContextTurnRouter().decide(request, session)
    candidates = SemanticRetriever(PACKAGE_DIR).retrieve(message)
    llm = RuleBasedMockLLMClient()
    analyst = DataAnalystPlannerAgent(
        AgentRuntime(
            llm=llm,
            system_prompt=(PROMPTS / "analyst_planner.md").read_text(encoding="utf-8"),
        )
    )
    draft = await analyst.plan(
        request=request,
        active_context=session.active_context,
        turn_decision=decision,
        candidates=candidates,
        current_time=datetime(2026, 8, 1, tzinfo=UTC),
        correlation_id="cor_query_a",
    )
    analysis, route = AnalysisPlanValidator().validate(draft, candidates, decision)
    assert route == "resolve"
    resolved = AnalysisPlanResolver(package).resolve(analysis)
    query_agent = LogicalQueryPlannerAgent(
        AgentRuntime(
            llm=llm,
            system_prompt=(PROMPTS / "logical_query_planner.md").read_text(encoding="utf-8"),
        )
    )
    query_draft = await query_agent.plan(
        analysis_plan=analysis,
        resolved_analysis=resolved,
        correlation_id="cor_query_b",
    )
    finalizer = QueryPlanFinalizer(
        index_router=IndexRouter(
            datasets=package.datasets(),
            policies=package.policies(),
            fields=package.fields(),
        ),
        budget=QueryBudget(),
    )
    query_plan = finalizer.finalize(query_draft, analysis, resolved)
    database.dispose()
    return package, analysis, resolved, query_draft, query_plan, llm


@pytest.mark.asyncio
async def test_agent_b_plan_is_logical_and_compiler_emits_valid_read_only_dsl() -> None:
    package, analysis, resolved, draft, plan, llm = await _plans("查询2026年7月各Channel失败率")
    assert plan.analysis_plan_id == analysis.object_id == resolved.analysis_plan_id
    assert plan.steps[0].index_patterns == ("tbl_os_sub_message_2026_07",)
    assert "query_dsl" not in draft.model_dump_json()
    assert "SearchIndexTool" not in draft.model_dump_json()

    compiler = DslCompiler(fields=package.fields(), metrics=package.metrics())
    compiled = compiler.compile(plan, "q1_base")
    CompiledQueryValidator(fields=package.fields(), policies=package.policies()).validate(
        compiled, plan
    )

    assert compiled.query_dsl["size"] == 0
    assert compiled.indices == ("tbl_os_sub_message_2026_07",)
    assert compiled.semantics.time_field_id == "sub_message.event_time"
    assert compiled.semantics.metric_ids == ("failure_rate.v1",)
    assert "script" not in compiled.model_dump_json()
    assert llm.calls == ["turn_and_analysis_plan", "logical_query_plan"]
    logical_payload = llm.input_payloads[1]
    logical_resolved = logical_payload["resolved"]
    assert isinstance(logical_resolved, dict)
    descriptors = logical_resolved["field_descriptors"]
    assert isinstance(descriptors, list)
    channel = next(item for item in descriptors if item["field_id"] == "sub_message.channel")
    assert channel["description"]
    assert channel["semantic_type"] == "categorical_dimension"
    assert "group_by" in channel["capabilities"]
    assert "physical_path" not in channel


@pytest.mark.asyncio
async def test_finalizer_rejects_dropped_metric_dimension_and_required_task() -> None:
    package, analysis, resolved, draft, _, _ = await _plans("查询2026年7月各Channel失败率")
    finalizer = QueryPlanFinalizer(
        index_router=IndexRouter(
            datasets=package.datasets(), policies=package.policies(), fields=package.fields()
        ),
        budget=QueryBudget(),
    )
    step = draft.steps[0]
    missing_status = step.model_copy(
        update={
            "dimensions": tuple(item for item in step.dimensions if item != "sub_message.status")
        }
    )
    with pytest.raises(QueryPlanFinalizationError, match="metric-required aggregation dimensions"):
        finalizer.finalize(
            draft.model_copy(update={"steps": (missing_status,)}), analysis, resolved
        )

    missing_task = step.model_copy(update={"purpose_task_ids": ()})
    with pytest.raises(QueryPlanFinalizationError, match="required analytical tasks"):
        finalizer.finalize(draft.model_copy(update={"steps": (missing_task,)}), analysis, resolved)

    required_dimension = analysis.tasks[0].dimension_ids[0]
    insufficient_grain = step.model_copy(
        update={"dimensions": tuple(item for item in step.dimensions if item != required_dimension)}
    )
    with pytest.raises(QueryPlanFinalizationError, match="sufficient grain"):
        finalizer.finalize(
            draft.model_copy(update={"steps": (insufficient_grain,)}), analysis, resolved
        )


@pytest.mark.asyncio
async def test_finalizer_rejects_profiled_cardinality_above_bucket_budget() -> None:
    package, analysis, resolved, draft, _, _ = await _plans("查询2026年7月各Channel失败率")
    descriptors = tuple(
        item.model_copy(update={"cardinality_estimate": 6000, "cardinality_approximate": True})
        if item.field_id == "sub_message.channel"
        else item
        for item in resolved.field_descriptors
    )
    profiled = resolved.model_copy(update={"field_descriptors": descriptors})
    finalizer = QueryPlanFinalizer(
        index_router=IndexRouter(
            datasets=package.datasets(), policies=package.policies(), fields=package.fields()
        ),
        budget=QueryBudget(),
    )

    with pytest.raises(QueryPlanFinalizationError, match="cardinality exceeds"):
        finalizer.finalize(draft, analysis, profiled)


@pytest.mark.asyncio
async def test_finalizer_promotes_agent_bucket_underestimate_within_budget() -> None:
    package, analysis, resolved, draft, _, _ = await _plans("7月每天的消息趋势")
    plan = QueryPlanFinalizer(
        index_router=IndexRouter(
            datasets=package.datasets(), policies=package.policies(), fields=package.fields()
        ),
        budget=QueryBudget(),
    ).finalize(draft, analysis, resolved)

    assert draft.steps[0].estimated_buckets == 20
    assert plan.steps[0].estimated_buckets == 31


@pytest.mark.asyncio
async def test_composite_page_keeps_base_fingerprint_and_uses_server_after_key() -> None:
    package, _, _, _, plan, _ = await _plans("查询2026年7月各Channel失败率")
    large_step = plan.steps[0].model_copy(update={"estimated_buckets": 5000})
    large_plan = plan.model_copy(update={"steps": (large_step,), "total_estimated_buckets": 5000})
    compiler = DslCompiler(fields=package.fields(), metrics=package.metrics())
    first_page = compiler.compile(large_plan, "q1_base")
    next_page = compiler.compile_composite_page(
        first_page,
        after_key={"dim_00_channel": "SMS", "dim_01_status": "FAILED"},
    )
    assert first_page.query_fingerprint == next_page.query_fingerprint
    assert first_page.content_hash != next_page.content_hash
    assert "after" not in first_page.model_dump_json()
    assert '"after"' in next_page.model_dump_json()


@pytest.mark.asyncio
async def test_validator_rejects_injected_script_and_unresolved_physical_field() -> None:
    package, _, _, _, plan, _ = await _plans("Query July 2026 message failure rate by channel")
    compiled = DslCompiler(fields=package.fields(), metrics=package.metrics()).compile(
        plan, "q1_base"
    )
    validator = CompiledQueryValidator(fields=package.fields(), policies=package.policies())
    scripted = compiled.model_copy(
        update={"query_dsl": {**compiled.query_dsl, "script": {"source": "return 1"}}}
    )
    with pytest.raises(QueryValidationError, match="unapproved top-level clause"):
        validator.validate(scripted, plan)

    altered_dsl = compiled.model_copy(deep=True).query_dsl
    altered_dsl["query"] = {
        "bool": {
            "filter": [
                *altered_dsl["query"]["bool"]["filter"],  # type: ignore[index]
                {"term": {"secret.unresolved": "x"}},
            ]
        }
    }
    unresolved = compiled.model_copy(update={"query_dsl": altered_dsl})
    with pytest.raises(QueryValidationError, match="unresolved physical fields"):
        validator.validate(unresolved, plan)


@pytest.mark.asyncio
async def test_dependent_top_n_filter_comes_from_real_q1_result() -> None:
    package, analysis, resolved, draft, _, _ = await _plans("查询2026年7月各Channel失败率")
    q1 = draft.steps[0]
    q2 = q1.model_copy(
        update={
            "step_id": "q2_daily_top_channels",
            "result_contract_id": "dc_q2_daily_top_channels",
            "depends_on": (q1.step_id,),
            "parameter_bindings": (
                ParameterBinding(
                    parameter="channel_values",
                    source_dataset_contract=q1.result_contract_id,
                    selection="top_n",
                    metric_id="message_record_count",
                    n=2,
                ),
            ),
            "estimated_buckets": 800,
        }
    )
    dependent_draft = draft.model_copy(update={"steps": (q1, q2)})
    plan = QueryPlanFinalizer(
        index_router=IndexRouter(
            datasets=package.datasets(), policies=package.policies(), fields=package.fields()
        ),
        budget=QueryBudget(),
    ).finalize(dependent_draft, analysis, resolved)
    compiler = DslCompiler(fields=package.fields(), metrics=package.metrics())
    q1_compiled = compiler.compile(plan, q1.step_id)
    channel_aggregation = next(
        item.aggregation_name
        for item in q1_compiled.semantics.bucket_path
        if item.dimension_id == "sub_message.channel"
    )
    result = RawSearchResult(
        query_id=q1_compiled.object_id,
        took_ms=3,
        timed_out=False,
        shards=ShardSummary(total=1, successful=1, skipped=0, failed=0),
        aggregations={
            channel_aggregation: {
                "buckets": [
                    {"key": "EMAIL", "doc_count": 12},
                    {"key": "SMS", "doc_count": 30},
                    {"key": "PUSH", "doc_count": 4},
                ]
            }
        },
        raw_size_bytes=256,
    )
    gateway = MockOpenSearchGateway()
    gateway.register(q1_compiled.query_fingerprint, result)
    actual_q1_result = await gateway.execute_search(q1_compiled)
    binder = DependentQueryBinder()
    values = binder.values_from_result(q2.parameter_bindings[0], q1_compiled, actual_q1_result)
    assert values == ("SMS", "EMAIL")
    bound_q2 = binder.bind(plan.steps[1], {"channel_values": values})
    bound_plan = plan.model_copy(update={"steps": (plan.steps[0], bound_q2)})
    compiled_q2 = compiler.compile(bound_plan, bound_q2.step_id)
    q2_result = result.model_copy(update={"query_id": compiled_q2.object_id})
    gateway.register(compiled_q2.query_fingerprint, q2_result)
    assert await gateway.execute_search(compiled_q2) == q2_result
    assert gateway.total_calls == 2
    assert '"SMS"' in compiled_q2.model_dump_json()
    assert '"EMAIL"' in compiled_q2.model_dump_json()


@pytest.mark.asyncio
async def test_finalizer_rejects_a_second_dependent_query_round() -> None:
    package, analysis, resolved, draft, _, _ = await _plans(
        "Query July 2026 message failure rate by channel"
    )
    q1 = draft.steps[0]
    q2 = q1.model_copy(
        update={
            "step_id": "q2_top_channels",
            "result_contract_id": "dc_q2_top_channels",
            "depends_on": (q1.step_id,),
            "parameter_bindings": (
                ParameterBinding(
                    parameter="channel_values",
                    source_dataset_contract=q1.result_contract_id,
                    selection="top_n",
                    n=2,
                ),
            ),
        }
    )
    q3 = q2.model_copy(
        update={
            "step_id": "q3_forbidden_second_round",
            "result_contract_id": "dc_q3_forbidden_second_round",
            "depends_on": (q2.step_id,),
            "parameter_bindings": (
                ParameterBinding(
                    parameter="channel_values",
                    source_dataset_contract=q2.result_contract_id,
                    selection="top_n",
                    n=1,
                ),
            ),
        }
    )
    dependent_draft = draft.model_copy(update={"steps": (q1, q2, q3)})
    finalizer = QueryPlanFinalizer(
        index_router=IndexRouter(
            datasets=package.datasets(),
            policies=package.policies(),
            fields=package.fields(),
        ),
        budget=QueryBudget(),
    )
    with pytest.raises(ValueError, match="dependent query rounds exceed policy"):
        finalizer.finalize(dependent_draft, analysis, resolved)
