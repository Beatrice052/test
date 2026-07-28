from __future__ import annotations

from pathlib import Path

from app.config.settings import Settings
from app.gateway.mock import MockOpenSearchGateway
from app.gateway.models import GatewayCapabilities, GatewayFault
from app.intent.mock_client import MockLLMClient
from app.intent.models import ConversationContext
from app.query.dsl import QueryDslBuilder
from app.query.planner import QueryPlanBuilder
from app.query.validator import QueryDslValidator
from app.semantic.compiler import SemanticCompiler, SemanticSourcePaths
from app.semantic.resolver import SemanticResolver

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _model():
    return SemanticCompiler(SemanticSourcePaths.from_project_root(PROJECT_ROOT)).compile().model


def _gateway(
    *, fault: GatewayFault = GatewayFault.NONE, msearch: bool = True
) -> MockOpenSearchGateway:
    return MockOpenSearchGateway(
        PROJECT_ROOT / "mock_data",
        PROJECT_ROOT / "semantic_sources" / "mock_mapping.json",
        fault=fault,
        capabilities=GatewayCapabilities(msearch=msearch),
    )


def _queries(question: str):
    model = _model()
    outcome = MockLLMClient(Settings()).create_analysis_plan(
        question, ConversationContext(business_timezone="Asia/Hong_Kong")
    )
    assert outcome.plan is not None
    resolution = SemanticResolver(model).resolve(outcome.plan)
    plans = QueryPlanBuilder(model).build(
        outcome.plan,
        resolution,
        available_indices=set(_gateway().list_indices()),
    )
    queries = []
    for plan in plans:
        for query in QueryDslBuilder(model).build(plan):
            queries.append(QueryDslValidator(model).validate(query)[0])
    return plans, queries


def test_mock_inventory_contains_multiple_months() -> None:
    assert _gateway().list_indices() == [
        "tbl_os_sub_message_2026_06",
        "tbl_os_sub_message_2026_07",
        "tbl_os_sub_message_2026_08",
    ]


def test_pure_count_selects_count_tool_and_returns_document_count() -> None:
    _, queries = _queries("2026年7月一共有多少条记录？")
    gateway = _gateway()

    steps = gateway.plan_execution(queries)
    bundle = gateway.execute(queries)

    assert steps[0].mcp_tool == "CountTool"
    assert steps[0].reason_code == "PURE_COUNT"
    assert bundle.results[0].payload["count"] == 186


def test_aggregation_selects_search_tool() -> None:
    _, queries = _queries("2026年7月各Channel Failure Rate")
    gateway = _gateway()

    step = gateway.plan_execution(queries)[0]
    bundle = gateway.execute(queries)

    assert step.mcp_tool == "SearchIndexTool"
    buckets = bundle.results[0].payload["aggregations"]["primary_group"]["buckets"]
    assert {bucket["key"] for bucket in buckets} == {"SMS", "Email", "WhatsApp"}
    assert sum(bucket["doc_count"] for bucket in buckets) == 186


def test_cross_month_independent_queries_select_msearch() -> None:
    _, queries = _queries("2026年6月至8月一共有多少条记录？")
    gateway = _gateway()

    steps = gateway.plan_execution(queries)
    bundle = gateway.execute(queries)

    assert len(steps) == 1
    assert steps[0].mcp_tool == "MsearchTool"
    assert len(bundle.results) == 3
    assert sum(result.payload["hits"]["total"]["value"] for result in bundle.results) == 552


def test_msearch_unavailable_falls_back_without_generic_or_ppl() -> None:
    _, queries = _queries("2026年6月至8月一共有多少条记录？")
    gateway = _gateway(msearch=False)

    steps = gateway.plan_execution(queries)

    assert len(steps) == 3
    assert {step.mcp_tool for step in steps} == {"CountTool"}
    assert gateway.capabilities().generic_api is False
    assert gateway.capabilities().ppl is False


def test_status_filter_normalizes_trim_and_case() -> None:
    _, queries = _queries("2026年7月哪个Route的失败记录最多？")
    bundle = _gateway().execute(queries)

    total = bundle.results[0].payload["hits"]["total"]["value"]

    assert total > 0
    assert total < 186


def test_fault_injection_is_visible_in_raw_metadata() -> None:
    _, queries = _queries("2026年7月各Channel Failure Rate")

    timeout = _gateway(fault=GatewayFault.QUERY_TIMEOUT).execute(queries)
    shard = _gateway(fault=GatewayFault.SHARD_FAILURE).execute(queries)

    assert timeout.results[0].payload["timed_out"] is True
    assert shard.results[0].payload["_shards"]["failed"] == 1
