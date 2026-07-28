from __future__ import annotations

from app.agent.contracts import AnalysisType
from app.config.settings import Settings
from app.intent.mock_client import MockLLMClient
from app.intent.models import ConversationContext


def _client() -> MockLLMClient:
    return MockLLMClient(Settings())


def _context() -> ConversationContext:
    return ConversationContext(business_timezone="Asia/Hong_Kong")


def test_failure_rate_by_channel_produces_structured_plan() -> None:
    outcome = _client().create_analysis_plan("2026年7月各Channel的Failure Rate是多少？", _context())

    assert outcome.plan is not None
    assert outcome.plan.analysis_type == AnalysisType.METRIC_BREAKDOWN
    assert outcome.plan.metric_concepts == ["failure_rate"]
    assert outcome.plan.dimension_concepts == ["channel"]
    assert outcome.plan.time_range.from_.month == 7
    assert outcome.plan.time_range.to.month == 8
    assert outcome.warnings == []


def test_default_time_is_visible_warning_not_unbounded_query() -> None:
    outcome = _client().create_analysis_plan("记录数量是多少？", _context())

    assert outcome.plan is not None
    assert outcome.plan.time_range.type == "configured_default"
    assert outcome.warnings == ["DEFAULT_TIME_RANGE"]


def test_ambiguous_failure_request_asks_one_question() -> None:
    outcome = _client().create_analysis_plan("看看最近的失败情况。", _context())

    assert outcome.plan is None
    assert outcome.clarification_slot == "breakdown_dimension"
    assert outcome.clarification_choices == ["channel", "route", "date_trend"]


def test_cross_month_question_has_half_open_range() -> None:
    outcome = _client().create_analysis_plan("2026年6月至8月一共有多少条记录？", _context())

    assert outcome.plan is not None
    assert outcome.plan.time_range.from_.isoformat() == "2026-06-01T00:00:00+08:00"
    assert outcome.plan.time_range.to.isoformat() == "2026-09-01T00:00:00+08:00"


def test_failure_record_top_route_uses_status_filter_not_failure_rate() -> None:
    outcome = _client().create_analysis_plan("哪个Route的失败记录最多？", _context())

    assert outcome.plan is not None
    assert outcome.plan.analysis_type == AnalysisType.TOP_N
    assert outcome.plan.metric_concepts == []
    assert outcome.plan.dimension_concepts == ["route"]
    assert outcome.plan.filter_concepts[0].concept == "status"
    assert outcome.plan.filter_concepts[0].values == ["FAILED", "ACKFAIL"]


def test_channel_comparison_is_breakdown_with_two_value_filter() -> None:
    outcome = _client().create_analysis_plan("比较SMS和Email的记录数量。", _context())

    assert outcome.plan is not None
    assert outcome.plan.analysis_type == AnalysisType.TERMS_BREAKDOWN
    assert outcome.plan.dimension_concepts == ["channel"]
    assert outcome.plan.filter_concepts[0].values == ["SMS", "Email"]


def test_status_distribution_without_physical_name_remains_ambiguous() -> None:
    outcome = _client().create_analysis_plan("按状态分析记录分布", _context())

    assert outcome.plan is not None
    assert outcome.plan.dimension_concepts == ["ambiguous_status"]


def test_explicit_day_range_becomes_half_open_business_time() -> None:
    outcome = _client().create_analysis_plan(
        "2026年7月3日至2026年7月10日每天有多少记录？", _context()
    )

    assert outcome.plan is not None
    assert outcome.plan.time_range.from_.isoformat() == "2026-07-03T00:00:00+08:00"
    assert outcome.plan.time_range.to.isoformat() == "2026-07-11T00:00:00+08:00"
    assert outcome.warnings == []


def test_carrier_specific_failure_rate_is_not_silently_mapped_to_v1() -> None:
    outcome = _client().create_analysis_plan("2026年7月中国移动失败率是多少？", _context())

    assert outcome.plan is not None
    assert outcome.plan.metric_concepts == ["carrier_failure_rate"]
