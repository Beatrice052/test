"""Fixture LLM returns exact JSON through the same strict schema boundary."""

from pathlib import Path

import pytest

from app.contracts.analysis import AnalysisPlanDraft
from app.contracts.query import QueryPlanDraft
from app.llm.fixture import FixtureLLMClient, FixtureNotFoundError

FIXTURE = Path(__file__).parents[4] / "fixtures" / "llm" / "analysis_plans.json"


@pytest.mark.asyncio
async def test_checked_in_fixture_is_strict_and_exact() -> None:
    client = FixtureLLMClient.from_file(FIXTURE)
    result = await client.generate(
        operation="turn_and_analysis_plan",
        system_prompt="fixed",
        input_payload={"fixture_id": "default"},
        output_schema=AnalysisPlanDraft,
        timeout_seconds=1,
        correlation_id="cor_fixture",
    )
    assert result.scope.dataset_ids == ("sub_message",)
    assert result.metric_decisions[0].metric_id == "message_record_count.v1"
    assert client.calls == [("turn_and_analysis_plan", "cor_fixture")]

    with pytest.raises(FixtureNotFoundError):
        await client.generate(
            operation="turn_and_analysis_plan",
            system_prompt="fixed",
            input_payload={"fixture_id": "missing"},
            output_schema=AnalysisPlanDraft,
            timeout_seconds=1,
            correlation_id="cor_missing",
        )


@pytest.mark.asyncio
async def test_fixture_interpolates_only_declared_dynamic_object_ids() -> None:
    client = FixtureLLMClient.from_file(FIXTURE)
    result = await client.generate(
        operation="logical_query_plan",
        system_prompt="fixed",
        input_payload={"fixture_id": "default", "resolved": {"analysis_plan_id": "ap_runtime"}},
        output_schema=QueryPlanDraft,
        timeout_seconds=1,
        correlation_id="cor_query_fixture",
    )
    assert result.analysis_plan_id == "ap_runtime"
    assert result.steps[0].dataset_id == "sub_message"
