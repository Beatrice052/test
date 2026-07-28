from __future__ import annotations

from pathlib import Path

from app.config.settings import Settings
from app.intent.mock_client import MockLLMClient
from app.intent.models import ConversationContext
from app.semantic.compiler import SemanticCompiler, SemanticSourcePaths
from app.semantic.resolver import AnswerabilityStatus, SemanticResolver

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _components() -> tuple[MockLLMClient, SemanticResolver]:
    model = SemanticCompiler(SemanticSourcePaths.from_project_root(PROJECT_ROOT)).compile().model
    return MockLLMClient(Settings()), SemanticResolver(model)


def _plan(question: str):
    client, _ = _components()
    outcome = client.create_analysis_plan(
        question, ConversationContext(business_timezone="Asia/Hong_Kong")
    )
    assert outcome.plan is not None
    return outcome.plan


def test_failure_rate_binding_comes_from_registry() -> None:
    _, resolver = _components()

    result = resolver.resolve(_plan("7月各Channel Failure Rate"))

    assert result.status == AnswerabilityStatus.ANSWERABLE_WITH_CAVEAT
    assert result.field_resolution["lifecycle_status"] == "status"
    assert result.field_resolution["channel"] == "channel"
    assert result.metric_resolution["failure_rate"] == "failure_rate.v1"
    assert "POC_METRIC" in result.reason_codes


def test_undefined_metric_is_not_invented() -> None:
    _, resolver = _components()

    result = resolver.resolve(_plan("7月SLA是多少？"))

    assert result.status == AnswerabilityStatus.METRIC_NOT_DEFINED


def test_blocked_message_body_is_stopped_before_query_plan() -> None:
    _, resolver = _components()

    result = resolver.resolve(_plan("7月按消息正文分析"))

    assert result.status == AnswerabilityStatus.POLICY_BLOCKED
    assert result.field_resolution == {}


def test_ambiguous_status_asks_status_or_status_code() -> None:
    _, resolver = _components()

    result = resolver.resolve(_plan("7月按状态分析记录分布"))

    assert result.status == AnswerabilityStatus.NEEDS_CLARIFICATION
    assert result.clarification_choices == ["status", "statusCode"]
