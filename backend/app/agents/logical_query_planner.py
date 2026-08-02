"""Agent B: logical dataset and query-step planning over already resolved IDs."""

from __future__ import annotations

from app.agents.base import AgentRuntime
from app.contracts.analysis import AnalysisPlan, ResolvedAnalysis
from app.contracts.query import QueryPlanDraft
from app.llm.redaction import redact_secrets
from app.llm.repair import build_query_plan_repair_payload


class LogicalQueryPlannerAgent:
    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime

    async def plan(
        self,
        *,
        analysis_plan: AnalysisPlan,
        resolved_analysis: ResolvedAnalysis,
        correlation_id: str,
        fixture_id: str | None = None,
    ) -> QueryPlanDraft:
        payload: dict[str, object] = {
            "analysis_plan": analysis_plan.model_dump(mode="json"),
            "resolved": {
                "analysis_plan_id": resolved_analysis.analysis_plan_id,
                "dataset_ids": list(resolved_analysis.dataset_ids),
                "index_route_candidates": list(resolved_analysis.index_patterns),
                "resolved_field_ids": list(resolved_analysis.resolved_field_ids),
                "metrics": [
                    {
                        "metric_id": metric.metric_id,
                        "version": metric.version,
                        "required_field_ids": list(metric.required_field_ids),
                        "required_grain": list(metric.required_grain),
                        "executable": metric.executable,
                    }
                    for metric in resolved_analysis.metrics
                ],
                "filters": [
                    {
                        "field_id": item.field_id,
                        "operator": item.operator,
                        "values": list(item.values),
                    }
                    for item in resolved_analysis.filters
                ],
                "time_field_id": resolved_analysis.time_field_id,
                "time_range": resolved_analysis.time_range.model_dump(mode="json"),
                "method_ids": list(resolved_analysis.method_ids),
                "policy_scope_id": resolved_analysis.policy_scope_id,
            },
            "result_grain_rules": {
                "stable_dimension_order": True,
                "result_contract_required": True,
            },
            "budgets": {
                "max_queries": analysis_plan.budget.max_queries,
                "max_buckets": analysis_plan.budget.max_buckets,
                "max_dependent_query_rounds": 1,
                "timeout_ms": 30000,
            },
        }
        if fixture_id is not None:
            payload["fixture_id"] = fixture_id
        return await self.runtime.llm.generate(
            operation="logical_query_plan",
            system_prompt=self.runtime.system_prompt,
            input_payload=redact_secrets(payload),
            output_schema=QueryPlanDraft,
            timeout_seconds=self.runtime.timeout_seconds,
            correlation_id=correlation_id,
        )

    async def repair(
        self,
        *,
        draft: QueryPlanDraft,
        errors: tuple[str, ...],
        analysis_plan: AnalysisPlan,
        resolved_analysis: ResolvedAnalysis,
        attempt: int,
        correlation_id: str,
        fixture_id: str | None = None,
    ) -> QueryPlanDraft:
        payload = build_query_plan_repair_payload(
            draft=draft,
            errors=errors,
            resolved=resolved_analysis,
            immutable_analysis_plan_hash=analysis_plan.content_hash,
            attempt=attempt,
            fixture_id=fixture_id,
        )
        return await self.runtime.llm.generate(
            operation="json_repair",
            system_prompt=self.runtime.system_prompt,
            input_payload=redact_secrets(payload),
            output_schema=QueryPlanDraft,
            timeout_seconds=self.runtime.timeout_seconds,
            correlation_id=correlation_id,
        )
