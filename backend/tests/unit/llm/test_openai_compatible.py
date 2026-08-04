"""OpenAI-compatible adapter preserves the strict no-tool structured boundary."""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ConfigDict

from app.contracts.common import StrictModel
from app.llm.openai_compatible import LLMAdapterError, OpenAICompatibleLLMClient


class SampleOutput(StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    answer: str


class AlternateOutput(StrictModel):
    value: int


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    (
        "turn_and_analysis_plan",
        "logical_query_plan",
        "post_query_visual_exploration",
        "post_query_insight_dashboard",
    ),
)
async def test_all_bounded_agent_operations_send_json_schema_without_tools(
    operation: str,
) -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        assert request.headers["x-correlation-id"] == "corr-1"
        assert request.headers["authorization"] == "Bearer placeholder"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"answer":"ok"}'}}]},
        )

    client = OpenAICompatibleLLMClient(
        base_url="https://llm.internal.example/v1",
        model="approved-model",
        api_key=__import__("pydantic").SecretStr("placeholder"),
        transport=httpx.MockTransport(handler),
    )
    result = await client.generate(
        operation=operation,  # type: ignore[arg-type]
        system_prompt="Return one schema-valid object.",
        input_payload={"text": "safe"},
        output_schema=SampleOutput,
        timeout_seconds=1,
        correlation_id="corr-1",
    )

    assert result.answer == "ok"
    assert captured["model"] == "approved-model"
    assert "tools" not in captured
    assert "tool_choice" not in captured
    assert captured["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": f"{operation}_SampleOutput",
            "strict": True,
            "schema": SampleOutput.model_json_schema(),
        },
    }


@pytest.mark.asyncio
async def test_rejects_non_schema_response_without_leaking_body() -> None:
    secret_response = "credential-that-must-not-leak"

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": secret_response}}]},
        )

    client = OpenAICompatibleLLMClient(
        base_url="https://llm.internal.example/v1/chat/completions",
        model="approved-model",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(LLMAdapterError) as captured:
        await client.generate(
            operation="semantic_query_rewrite",
            system_prompt="strict",
            input_payload={},
            output_schema=SampleOutput,
            timeout_seconds=1,
            correlation_id="corr-2",
        )
    assert secret_response not in str(captured.value)


@pytest.mark.asyncio
async def test_shared_repair_operation_uses_contract_specific_schema_names() -> None:
    schema_names: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        schema_names.append(body["response_format"]["json_schema"]["name"])
        content = '{"answer":"ok"}' if len(schema_names) == 1 else '{"value":1}'
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    client = OpenAICompatibleLLMClient(
        base_url="https://llm.internal.example/v1",
        model="approved-model",
        transport=httpx.MockTransport(handler),
    )
    await client.generate(
        operation="json_repair",
        system_prompt="strict",
        input_payload={},
        output_schema=SampleOutput,
        timeout_seconds=1,
        correlation_id="corr-repair-1",
    )
    await client.generate(
        operation="json_repair",
        system_prompt="strict",
        input_payload={},
        output_schema=AlternateOutput,
        timeout_seconds=1,
        correlation_id="corr-repair-2",
    )

    assert schema_names == ["json_repair_SampleOutput", "json_repair_AlternateOutput"]


@pytest.mark.asyncio
async def test_rejects_unapproved_operation_before_network() -> None:
    called = False

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    client = OpenAICompatibleLLMClient(
        base_url="https://llm.internal.example/v1",
        model="approved-model",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ValueError, match="operation is not allowed"):
        await client.generate(
            operation="chat",
            system_prompt="strict",
            input_payload={},
            output_schema=SampleOutput,
            timeout_seconds=1,
            correlation_id="corr-3",
        )
    assert called is False
