"""The only interface available to an LLM-backed node."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

OutputModel = TypeVar("OutputModel", bound=BaseModel)

ALLOWED_OPERATIONS = frozenset(
    {
        "turn_and_analysis_plan",
        "logical_query_plan",
        "post_query_insight_dashboard",
        "semantic_query_rewrite",
        "json_repair",
    }
)


class StructuredLLMClient(Protocol):
    async def generate(
        self,
        *,
        operation: str,
        system_prompt: str,
        input_payload: dict[str, object],
        output_schema: type[OutputModel],
        timeout_seconds: float,
        correlation_id: str,
    ) -> OutputModel: ...
