from __future__ import annotations

from pathlib import Path

from app.config.settings import Settings
from app.gateway.mock import MockOpenSearchGateway
from app.gateway.models import GatewayFault
from app.intent.mock_client import MockLLMClient
from app.intent.models import ConversationContext
from app.metrics.engine import MetricEngine
from app.query.dsl import QueryDslBuilder
from app.query.planner import QueryPlanBuilder
from app.query.validator import QueryDslValidator
from app.results.models import QualityStatus
from app.results.processor import ResultProcessor
from app.semantic.compiler import SemanticCompiler, SemanticSourcePaths
from app.semantic.resolver import SemanticResolver

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _run(question: str, *, fault: GatewayFault = GatewayFault.NONE):
    model = SemanticCompiler(SemanticSourcePaths.from_project_root(PROJECT_ROOT)).compile().model
    gateway = MockOpenSearchGateway(
        PROJECT_ROOT / "mock_data",
        PROJECT_ROOT / "semantic_sources" / "mock_mapping.json",
        fault=fault,
    )
    intent = MockLLMClient(Settings()).create_analysis_plan(
        question, ConversationContext(business_timezone="Asia/Hong_Kong")
    )
    assert intent.plan is not None
    resolution = SemanticResolver(model).resolve(intent.plan)
    plan = QueryPlanBuilder(model).build(
        intent.plan, resolution, available_indices=set(gateway.list_indices())
    )[0]
    queries = [
        QueryDslValidator(model).validate(query)[0] for query in QueryDslBuilder(model).build(plan)
    ]
    bundle = gateway.execute(queries)
    processed = ResultProcessor(model).process(plan, bundle.results)
    return processed, bundle


def test_failure_rate_uses_half_up_rounding_and_zero_denominator_null() -> None:
    engine = MetricEngine()

    normal = engine.failure_rate(3, 1, 1)
    empty = engine.failure_rate(0, 0, 0)

    assert normal.failure_rate == 33.33
    assert empty.failure_rate is None
    assert empty.other_count == 0


def test_cross_month_count_merges_document_counts() -> None:
    processed, _ = _run("2026年6月至8月一共有多少条记录？")

    assert processed.prepared_data.totals["total_count"] == 552
    assert processed.prepared_data.quality.status == QualityStatus.PASSED
    assert processed.prepared_data.provenance["indices"] == [
        "tbl_os_sub_message_2026_06",
        "tbl_os_sub_message_2026_07",
        "tbl_os_sub_message_2026_08",
    ]


def test_grouped_failure_rate_reconciles_and_produces_chart() -> None:
    processed, _ = _run("2026年7月各Channel Failure Rate")

    rows = processed.prepared_data.rows
    totals = processed.prepared_data.totals
    assert len(rows) == 3
    assert sum(row["total_count"] for row in rows) == totals["total_count"] == 186
    assert (
        totals["total_success_count"] + totals["total_failed_count"] + totals["other_count"] == 186
    )
    assert processed.prepared_data.quality.status == QualityStatus.PASSED
    assert processed.chart is not None
    assert processed.chart.type == "bar"
    assert processed.chart.y_field == "failure_rate"


def test_daily_trend_includes_zero_buckets_and_line_chart() -> None:
    processed, _ = _run("2026年7月SMS每天的发送记录趋势是什么？")

    assert len(processed.prepared_data.rows) == 31
    assert processed.chart is not None
    assert processed.chart.type == "line"
    assert processed.prepared_data.quality.status == QualityStatus.PASSED


def test_no_data_failure_rate_returns_null_not_zero() -> None:
    processed, _ = _run("2026年7月空结果 Failure Rate")

    assert processed.prepared_data.totals["total_count"] == 0
    assert processed.prepared_data.totals["failure_rate"] is None
    assert processed.prepared_data.quality.status == QualityStatus.PASSED


def test_timeout_and_metric_corruption_fail_qa() -> None:
    timeout, _ = _run("2026年7月各Channel Failure Rate", fault=GatewayFault.QUERY_TIMEOUT)
    corrupt, _ = _run("2026年7月各Channel Failure Rate", fault=GatewayFault.METRIC_QA_FAILED)

    assert timeout.prepared_data.quality.status == QualityStatus.FAILED
    assert corrupt.prepared_data.quality.status == QualityStatus.FAILED
