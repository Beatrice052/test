"""Minimal directed-repair payload; never resends history, schema, or credentials."""

from app.contracts.analysis import AnalysisPlanDraft, ResolvedAnalysis, TurnDecision
from app.contracts.common import semantic_hash
from app.contracts.dataset import DatasetBundle
from app.contracts.insight import InsightDashboardDraft
from app.contracts.query import QueryPlanDraft
from app.contracts.semantic import SemanticCandidateSet


def build_analysis_plan_repair_payload(
    *,
    draft: AnalysisPlanDraft,
    errors: tuple[str, ...],
    candidates: SemanticCandidateSet,
    decision: TurnDecision,
    immutable_question_hash: str,
    attempt: int,
    fixture_id: str | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "original_output": draft.model_dump(mode="json"),
        "validator_error_codes": list(errors),
        "allowed_ids": {
            "dataset": [item.item_id for item in candidates.dataset_candidates],
            "metric": [item.item_id for item in candidates.metric_candidates],
            "field": [item.item_id for item in candidates.field_candidates],
            "method": [item.item_id for item in candidates.method_candidates],
        },
        "authoritative_turn_kind": decision.turn_kind.value,
        "immutable_question_hash": immutable_question_hash,
        "original_output_hash": semantic_hash(draft),
        "attempt": attempt,
    }
    if fixture_id is not None:
        payload["fixture_id"] = fixture_id
    return payload


def build_query_plan_repair_payload(
    *,
    draft: QueryPlanDraft,
    errors: tuple[str, ...],
    resolved: ResolvedAnalysis,
    immutable_analysis_plan_hash: str,
    attempt: int,
    fixture_id: str | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "original_output": draft.model_dump(mode="json"),
        "validator_error_codes": list(errors),
        "allowed_ids": {
            "dataset": list(resolved.dataset_ids),
            "field": list(resolved.resolved_field_ids),
            "metric": [f"{item.metric_id}.{item.version}" for item in resolved.metrics],
            "index": list(resolved.index_patterns),
            "method": list(resolved.method_ids),
        },
        "authoritative_analysis_plan_id": resolved.analysis_plan_id,
        "authoritative_time_field_id": resolved.time_field_id,
        "authoritative_time_range": resolved.time_range.model_dump(mode="json"),
        "immutable_analysis_plan_hash": immutable_analysis_plan_hash,
        "original_output_hash": semantic_hash(draft),
        "attempt": attempt,
    }
    if fixture_id is not None:
        payload["fixture_id"] = fixture_id
    return payload


def build_insight_dashboard_repair_payload(
    *,
    draft: InsightDashboardDraft,
    errors: tuple[str, ...],
    bundle: DatasetBundle,
    immutable_analysis_plan_hash: str,
    required_task_ids: tuple[str, ...],
    preview_ids: tuple[str, ...],
    attempt: int,
    fixture_id: str | None,
) -> dict[str, object]:
    """Build a bounded Agent C repair request without query DSL or full rows."""

    payload: dict[str, object] = {
        "original_output": draft.model_dump(mode="json"),
        "validator_error_codes": list(errors),
        "allowed_ids": {
            "dataset_columns": {
                item.dataset_id: [column.name for column in item.columns]
                for item in bundle.datasets
            },
            "visualization_dataset": [item.dataset_id for item in bundle.datasets],
            "required_task": list(required_task_ids),
            "visualization_preview": list(preview_ids),
        },
        "immutable_analysis_plan_hash": immutable_analysis_plan_hash,
        "immutable_dataset_bundle_hash": bundle.content_hash,
        "original_output_hash": semantic_hash(draft),
        "attempt": attempt,
    }
    if fixture_id is not None:
        payload["fixture_id"] = fixture_id
    return payload
