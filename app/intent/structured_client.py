from __future__ import annotations

from typing import Any, Protocol

from pydantic import TypeAdapter

from app.config.settings import Settings
from app.intent.models import ConversationContext, IntentOutcome
from app.semantic.models import CompiledSemanticModel, FieldAccess


class StructuredLLMTransport(Protocol):
    """Provider-specific boundary implemented inside the internal network.

    Implementations may call the same approved LLM SDK/helper used by another
    internal project. Credentials, endpoints and provider response objects must
    remain behind this interface.
    """

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        json_schema: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]: ...

    def complete_text(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        timeout_seconds: int,
    ) -> str: ...


class StructuredLLMClient:
    """Strict real-LLM adapter for AnalysisPlan and safe result summaries.

    The class is provider-neutral and production-ready at the contract layer.
    The internal team only supplies StructuredLLMTransport using an approved
    local reference project.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        semantic_model: CompiledSemanticModel,
        transport: StructuredLLMTransport,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self.semantic_context = self._semantic_prompt_context(semantic_model)
        self._intent_adapter = TypeAdapter(IntentOutcome)

    def create_analysis_plan(self, question: str, context: ConversationContext) -> IntentOutcome:
        response = self.transport.complete_json(
            system_prompt=self._intent_system_prompt(),
            user_payload={
                "question": question,
                "conversation_context": context.model_dump(mode="json"),
                "semantic_context": self.semantic_context,
                "time_rules": {
                    "business_timezone": self.settings.business_timezone,
                    "default_from": self.settings.default_time_from.isoformat(),
                    "default_to": self.settings.default_time_to.isoformat(),
                    "interval": "[from,to)",
                },
            },
            json_schema=IntentOutcome.model_json_schema(),
            timeout_seconds=self.settings.llm_timeout_seconds,
        )
        return self._intent_adapter.validate_python(response)

    def summarize(self, question: str, prepared_data: dict, caveats: list[str]) -> str:
        text = self.transport.complete_text(
            system_prompt=self._summary_system_prompt(),
            user_payload={
                "question": question,
                "prepared_data": prepared_data,
                "caveats": caveats,
                "instruction": (
                    "Only summarize supplied deterministic results. "
                    "Do not calculate, infer missing values, or output HTML."
                ),
            },
            timeout_seconds=self.settings.llm_timeout_seconds,
        )
        normalized = text.strip()
        if not normalized:
            raise ValueError("LLM summary cannot be blank")
        return normalized

    @staticmethod
    def _semantic_prompt_context(
        model: CompiledSemanticModel,
    ) -> dict[str, Any]:
        allowed_fields = [
            {
                "concept": field.field_path,
                "aliases": field.aliases,
                "description": field.description,
                "allowed_operations": field.allowed_operations,
                "value_dictionary": field.value_dictionary,
                "caveats": field.analysis_caveats,
            }
            for field in model.fields
            if field.access is FieldAccess.ALLOWED
        ]
        return {
            "dataset_id": model.dataset.dataset_id,
            "allowed_fields": allowed_fields,
            "metrics": [
                {
                    "metric_id": metric.metric_id,
                    "version": metric.version,
                    "description": metric.description,
                    "caveats": metric.caveats,
                }
                for metric in model.metrics
            ],
            "semantic_model_version": model.model_version,
        }

    @staticmethod
    def _intent_system_prompt() -> str:
        return (
            "You are the intent-planning component of a controlled ChatBI system. "
            "Return only an object conforming to the supplied JSON Schema. "
            "AnalysisPlan describes what the user wants to analyze. Never emit "
            "OpenSearch DSL, index names, MCP tools, generic API calls, formulas, "
            "HTML, JavaScript, credentials, or fields absent from semantic_context. "
            "When a material slot is ambiguous, return one clarification question "
            "instead of guessing."
        )

    @staticmethod
    def _summary_system_prompt() -> str:
        return (
            "You summarize deterministic ChatBI results supplied by the backend. "
            "Do not recompute metrics, change denominators, invent causes, expose "
            "hidden fields, or output HTML/JavaScript. State no-data and caveats "
            "clearly and concisely."
        )
