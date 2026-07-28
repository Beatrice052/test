from __future__ import annotations

from pathlib import Path

import pytest

from app.config.settings import Settings
from app.intent.mock_client import MockLLMClient
from app.intent.models import ConversationContext
from app.query.dsl import QueryDslBuilder
from app.query.planner import QueryPlanBuilder
from app.query.validator import QueryDslValidator, QueryValidationError
from app.semantic.compiler import SemanticCompiler, SemanticSourcePaths
from app.semantic.resolver import SemanticResolver

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _compile(question: str):
    model = SemanticCompiler(SemanticSourcePaths.from_project_root(PROJECT_ROOT)).compile().model
    intent = MockLLMClient(Settings()).create_analysis_plan(
        question, ConversationContext(business_timezone="Asia/Hong_Kong")
    )
    assert intent.plan is not None
    resolution = SemanticResolver(model).resolve(intent.plan)
    plans = QueryPlanBuilder(model).build(intent.plan, resolution)
    compiled = QueryDslBuilder(model).build(plans[0])
    return model, plans[0], compiled


def test_pure_count_compiles_to_query_without_aggregation() -> None:
    model, plan, compiled = _compile("2026年7月一共有多少条记录？")

    assert plan.physical_indices == ["tbl_os_sub_message_2026_07"]
    assert len(compiled) == 1
    assert (
        compiled[0].body["query"]["bool"]["filter"][0]["range"]["createdTime"]["lt"]
        == "2026-08-01T00:00:00+08:00"
    )
    assert "aggs" not in compiled[0].body
    validated, result = QueryDslValidator(model).validate(compiled[0])
    assert validated.validation_status == "PASSED"
    assert result.status == "PASSED"


def test_failure_rate_by_channel_uses_group_and_status_filters() -> None:
    model, _, compiled = _compile("2026年7月各Channel Failure Rate")

    body = compiled[0].body
    group = body["aggs"]["primary_group"]
    assert group["terms"]["field"] == "channel"
    assert group["aggs"]["success"]["filter"]["terms"]["status"] == [
        "SENT",
        "INPROGRESS",
    ]
    assert group["aggs"]["failed"]["filter"]["terms"]["status"] == [
        "FAILED",
        "ACKFAIL",
    ]
    QueryDslValidator(model).validate(compiled[0])


def test_cross_month_plan_expands_to_one_compiled_query_per_index() -> None:
    _, plan, compiled = _compile("2026年6月至8月一共有多少条记录？")

    assert len(plan.physical_indices) == 3
    assert len(compiled) == 3
    assert {query.index for query in compiled} == {
        "tbl_os_sub_message_2026_06",
        "tbl_os_sub_message_2026_07",
        "tbl_os_sub_message_2026_08",
    }


def test_validator_rejects_script_even_when_other_fields_are_valid() -> None:
    model, _, compiled = _compile("2026年7月一共有多少条记录？")
    malicious = compiled[0].model_copy(
        update={"body": {**compiled[0].body, "script_fields": {"x": {"script": "1"}}}},
        deep=True,
    )

    with pytest.raises(QueryValidationError) as captured:
        QueryDslValidator(model).validate(malicious)

    assert any(
        check.name == "forbidden_dsl" and not check.passed for check in captured.value.result.checks
    )


def test_validator_rejects_blocked_field_reference() -> None:
    model, _, compiled = _compile("2026年7月一共有多少条记录？")
    blocked = compiled[0].model_copy(
        update={
            "body": {
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"messageBody": "secret"}},
                        ]
                    }
                }
            }
        },
        deep=True,
    )

    with pytest.raises(QueryValidationError) as captured:
        QueryDslValidator(model).validate(blocked)

    assert any(
        check.name == "field_exists" and not check.passed for check in captured.value.result.checks
    )
