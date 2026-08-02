"""Agent A: construct minimal input and request one AnalysisPlanDraft."""

from __future__ import annotations

from datetime import datetime

from app.agents.base import AgentRuntime
from app.contracts.analysis import AnalysisPlanDraft, TurnDecision
from app.contracts.request import ChatRequest
from app.contracts.semantic import CandidateItem, SemanticCandidateSet
from app.contracts.session import ActiveAnalyticalContext
from app.llm.redaction import redact_secrets
from app.llm.repair import build_analysis_plan_repair_payload


class DataAnalystPlannerAgent:
    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime

    async def plan(
        self,
        *,
        request: ChatRequest,
        active_context: ActiveAnalyticalContext,
        turn_decision: TurnDecision,
        candidates: SemanticCandidateSet,
        current_time: datetime,
        correlation_id: str,
        fixture_id: str | None = None,
    ) -> AnalysisPlanDraft:
        payload: dict[str, object] = {
            "user_message": request.message,
            "locale": "zh-CN",
            "current_time": current_time.isoformat(),
            "session_active_context": active_context.model_dump(mode="json"),
            "turn_classification": {
                "agent_must_decide": True,
                "provisional_hint": turn_decision.turn_kind.value,
                "has_previous_answer": active_context.analytical_base_answer_id is not None,
                "allowed_turn_kinds": [
                    "NEW_ANALYSIS",
                    "CLARIFICATION",
                    "FILTER_CHANGE",
                    "TIME_CHANGE",
                    "DIMENSION_CHANGE",
                    "PRESENTATION_CHANGE",
                    "EXPLANATION",
                    "NEW_TOPIC",
                ],
            },
            "presentation_catalog": {
                "agent_must_interpret_explicit_user_preference": True,
                "allowed_chart_types": [
                    "bar",
                    "line",
                    "heatmap",
                    "stacked_bar",
                    "donut",
                    "dot",
                    "pareto",
                    "table",
                    "pivot",
                ],
                "unknown_requested_type_goes_to": "unsupported_chart_label",
            },
            "candidate_datasets": self._summaries(candidates.dataset_candidates),
            "candidate_metrics": self._summaries(candidates.metric_candidates),
            "candidate_fields": self._summaries(candidates.field_candidates),
            "candidate_recipes": self._summaries(candidates.recipe_candidates),
            "candidate_methods": self._summaries(candidates.method_candidates),
            "candidate_values": self._summaries(candidates.value_candidates),
            "policy_summary": {"candidate_ids_only": True},
            "budgets": {"max_queries": 3, "max_buckets": 5000, "max_blocks": 8},
        }
        if fixture_id is not None:
            payload["fixture_id"] = fixture_id
        return await self.runtime.llm.generate(
            operation="turn_and_analysis_plan",
            system_prompt=self.runtime.system_prompt,
            input_payload=redact_secrets(payload),
            output_schema=AnalysisPlanDraft,
            timeout_seconds=self.runtime.timeout_seconds,
            correlation_id=correlation_id,
        )

    async def repair(
        self,
        *,
        draft: AnalysisPlanDraft,
        errors: tuple[str, ...],
        candidates: SemanticCandidateSet,
        turn_decision: TurnDecision,
        immutable_question_hash: str,
        attempt: int,
        correlation_id: str,
        fixture_id: str | None = None,
    ) -> AnalysisPlanDraft:
        payload = build_analysis_plan_repair_payload(
            draft=draft,
            errors=errors,
            candidates=candidates,
            decision=turn_decision,
            immutable_question_hash=immutable_question_hash,
            attempt=attempt,
            fixture_id=fixture_id,
        )
        return await self.runtime.llm.generate(
            operation="json_repair",
            system_prompt=self.runtime.system_prompt,
            input_payload=redact_secrets(payload),
            output_schema=AnalysisPlanDraft,
            timeout_seconds=self.runtime.timeout_seconds,
            correlation_id=correlation_id,
        )

    @staticmethod
    def _summaries(items: tuple[CandidateItem, ...]) -> list[dict[str, object]]:
        return [
            {
                "item_id": item.item_id,
                "display_name": item.display_name,
                "summary": item.summary,
                "score": item.score,
                "capabilities": list(item.capabilities),
                "metadata": item.metadata,
            }
            for item in items
        ]
