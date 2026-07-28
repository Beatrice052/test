from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.config.settings import Settings
from app.intent.models import ConversationContext
from app.intent.structured_client import StructuredLLMClient
from app.semantic.compiler import SemanticCompiler, SemanticSourcePaths

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class FakeTransport:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.json_request: dict[str, Any] | None = None
        self.text_request: dict[str, Any] | None = None

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        json_schema: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        self.json_request = {
            "system_prompt": system_prompt,
            "user_payload": user_payload,
            "json_schema": json_schema,
            "timeout_seconds": timeout_seconds,
        }
        return self.response

    def complete_text(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        timeout_seconds: int,
    ) -> str:
        self.text_request = {
            "system_prompt": system_prompt,
            "user_payload": user_payload,
            "timeout_seconds": timeout_seconds,
        }
        return "结果来自确定性指标引擎。"


def _valid_response() -> dict[str, Any]:
    return {
        "plan": {
            "analysis_type": "count",
            "dataset_concept": "sub_message",
            "metric_concepts": [],
            "dimension_concepts": [],
            "filter_concepts": [],
            "time_range": {
                "type": "absolute_month",
                "from": "2026-07-01T00:00:00+08:00",
                "to": "2026-08-01T00:00:00+08:00",
                "grain": "day",
            },
            "comparison": None,
            "requested_outputs": ["kpi", "summary"],
        },
        "clarification_question": None,
        "clarification_slot": None,
        "clarification_choices": [],
        "warnings": [],
    }


def _client(transport: FakeTransport) -> StructuredLLMClient:
    model = SemanticCompiler(SemanticSourcePaths.from_project_root(PROJECT_ROOT)).compile().model
    return StructuredLLMClient(
        settings=Settings(intent_backend="structured_llm"),
        semantic_model=model,
        transport=transport,
    )


def test_real_llm_prompt_contains_only_allowed_semantic_fields() -> None:
    transport = FakeTransport(_valid_response())
    client = _client(transport)

    outcome = client.create_analysis_plan(
        "2026年7月记录数",
        ConversationContext(business_timezone="Asia/Hong_Kong"),
    )

    assert outcome.plan is not None
    assert outcome.plan.analysis_type == "count"
    assert transport.json_request is not None
    serialized = str(transport.json_request["user_payload"])
    for blocked in [
        "messageBody",
        "customerName",
        "phoneNumber",
        "emailAddress",
        "bankAccount",
        "customerId",
        "candidate_role",
    ]:
        assert blocked not in serialized


def test_real_llm_output_is_revalidated_against_strict_contract() -> None:
    response = _valid_response()
    assert response["plan"] is not None
    response["plan"]["mcp_tool"] = "GenericOpenSearchApiTool"
    client = _client(FakeTransport(response))

    with pytest.raises(ValidationError):
        client.create_analysis_plan(
            "count",
            ConversationContext(business_timezone="Asia/Hong_Kong"),
        )


def test_real_llm_summary_cannot_be_blank() -> None:
    transport = FakeTransport(_valid_response())
    client = _client(transport)
    transport.complete_text = lambda **_: "   "  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="cannot be blank"):
        client.summarize("count", {"totals": {"total_count": 1}}, [])
