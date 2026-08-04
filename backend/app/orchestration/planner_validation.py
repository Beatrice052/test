"""Candidate allowlist and answerability validation for Agent A output."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from app.contracts.analysis import (
    AnalysisBudget,
    AnalysisPlan,
    AnalysisPlanDraft,
    AnalysisScope,
    Clarification,
    TurnDecision,
)
from app.contracts.common import Provenance, semantic_hash
from app.contracts.dashboard import VisualizationDefinition
from app.contracts.semantic import SemanticCandidateSet
from app.orchestration.routes import AnalysisRoute
from app.persistence.ids import new_id


class AnalysisPlanValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class AnalysisPlanValidator:
    def __init__(
        self,
        visualization_definitions: tuple[VisualizationDefinition, ...] = (),
        maximum_budget: AnalysisBudget | None = None,
    ) -> None:
        self.allowed_visualization_intents = {item.intent for item in visualization_definitions}
        self.allowed_chart_types = {
            chart_type
            for item in visualization_definitions
            for chart_type in item.allowed_chart_types
        } | {"table", "pivot"}
        self.maximum_budget = maximum_budget or AnalysisBudget()

    def validate(
        self,
        draft: AnalysisPlanDraft,
        candidates: SemanticCandidateSet,
        decision: TurnDecision,
    ) -> tuple[AnalysisPlan, AnalysisRoute]:
        if draft.turn_relation != decision.turn_kind:
            raise AnalysisPlanValidationError(
                "TURN_RELATION_MISMATCH", "draft changed the authoritative turn relation"
            )
        allowed_datasets = {item.item_id for item in candidates.dataset_candidates}
        allowed_metrics = {item.item_id for item in candidates.metric_candidates}
        allowed_fields = {item.item_id for item in candidates.field_candidates}
        allowed_methods = {item.item_id for item in candidates.method_candidates}
        self._require_unique(
            "DUPLICATE_METRIC_DECISION",
            "metric decision",
            (item.metric_id for item in draft.metric_decisions),
        )
        self._require_unique(
            "DUPLICATE_TASK_ID", "analytical task", (item.task_id for item in draft.tasks)
        )
        self._require_subset("dataset", draft.scope.dataset_ids, allowed_datasets)
        self._require_subset(
            "filter field", (item.field_id for item in draft.scope.filters), allowed_fields
        )
        self._require_subset(
            "metric", (item.metric_id for item in draft.metric_decisions), allowed_metrics
        )
        selected_metrics = {
            item.metric_id for item in draft.metric_decisions if item.decision != "rejected"
        }
        for task in draft.tasks:
            self._require_subset("task metric", task.metric_ids, allowed_metrics)
            unselected_metrics = set(task.metric_ids) - selected_metrics
            if unselected_metrics:
                raise AnalysisPlanValidationError(
                    "TASK_METRIC_NOT_SELECTED",
                    "analytical task references metrics that Agent A did not select: "
                    f"{sorted(unselected_metrics)}",
                )
            self._require_subset("task dimension", task.dimension_ids, allowed_fields)
            self._require_subset("task method", task.statistical_method_ids, allowed_methods)
            if self.allowed_visualization_intents:
                self._require_subset(
                    "visualization intent",
                    task.visualization_intents,
                    self.allowed_visualization_intents,
                )
        requested_chart_type = draft.presentation_preference.requested_chart_type
        if (
            requested_chart_type is not None
            and self.allowed_chart_types
            and requested_chart_type not in self.allowed_chart_types
        ):
            raise AnalysisPlanValidationError(
                "CHART_TYPE_NOT_AVAILABLE",
                f"requested chart type is not deployed: {requested_chart_type}",
            )
        if (
            draft.budget.max_queries > self.maximum_budget.max_queries
            or draft.budget.max_buckets > self.maximum_budget.max_buckets
            or draft.budget.max_blocks > self.maximum_budget.max_blocks
        ):
            raise AnalysisPlanValidationError(
                "PLAN_BUDGET_EXCEEDED",
                "Agent A cannot expand the server-provided analysis budget",
            )

        payload = draft.model_dump(mode="python")
        content_hash = semantic_hash(draft)
        plan = AnalysisPlan(
            object_id=new_id("ap"),
            created_at=datetime.now(UTC),
            content_hash=content_hash,
            provenance=Provenance(
                producer="orchestration.analysis_plan_validator",
                source_ids=(candidates.object_id, decision.object_id),
            ),
            **payload,
        )
        if plan.clarification is not None:
            route: AnalysisRoute = "clarify"
        elif not plan.scope.dataset_ids or not plan.tasks:
            route = "unanswerable"
        else:
            route = "resolve"
        return plan, route

    def safe_fallback(
        self,
        draft: AnalysisPlanDraft,
        candidates: SemanticCandidateSet,
        decision: TurnDecision,
    ) -> AnalysisPlan:
        allowed_datasets = tuple(item.item_id for item in candidates.dataset_candidates)
        fallback = AnalysisPlanDraft(
            analysis_goal=draft.analysis_goal,
            question_archetype=draft.question_archetype,
            turn_relation=decision.turn_kind,
            scope=AnalysisScope(
                dataset_ids=allowed_datasets[:1],
                time_range=draft.scope.time_range,
            ),
            metric_decisions=(),
            tasks=(),
            presentation_preference=draft.presentation_preference,
            clarification=Clarification(
                question="分析计划未通过候选 ID 校验, 请明确要分析的指标或维度。",
                reason_code="PLAN_VALIDATION_FAILED",
            ),
            assumptions=(),
            limitations=("结构化计划修复两次后仍不合法",),
            budget=self.maximum_budget,
        )
        plan, _ = self.validate(fallback, candidates, decision)
        return plan

    @staticmethod
    def _require_subset(label: str, values: Iterable[str], allowed: set[str]) -> None:
        actual = set(values)
        invented = actual - allowed
        if invented:
            raise AnalysisPlanValidationError(
                "CANDIDATE_ID_NOT_ALLOWED", f"{label} IDs were not candidates: {sorted(invented)}"
            )

    @staticmethod
    def _require_unique(code: str, label: str, values: Iterable[str]) -> None:
        items = tuple(values)
        duplicates = sorted({item for item in items if items.count(item) > 1})
        if duplicates:
            raise AnalysisPlanValidationError(code, f"{label} IDs are not unique: {duplicates}")
