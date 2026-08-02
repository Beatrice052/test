"""Agent C proposes grounded claim selectors and visualization intent, never numbers or code."""

from __future__ import annotations

from app.agents.base import AgentRuntime
from app.contracts.analysis import AnalysisPlan
from app.contracts.dashboard import VisualizationDefinition
from app.contracts.dataset import DatasetBundle
from app.contracts.insight import FeatureSummary, InsightDashboardDraft
from app.contracts.metric import MetricDefinition
from app.llm.redaction import redact_secrets
from app.llm.repair import build_insight_dashboard_repair_payload


class InsightDashboardAgent:
    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime

    async def plan(
        self,
        *,
        analysis_plan: AnalysisPlan,
        bundle: DatasetBundle,
        feature_summaries: tuple[FeatureSummary, ...],
        metric_definitions: tuple[MetricDefinition, ...],
        visualization_definitions: tuple[VisualizationDefinition, ...],
        correlation_id: str,
        fixture_id: str | None = None,
    ) -> InsightDashboardDraft:
        dataset_schemas = [
            {
                "dataset_id": item.dataset_id,
                "kind": item.kind,
                "grain": list(item.grain),
                "columns": [column.model_dump(mode="json") for column in item.columns],
                "completeness": item.completeness,
                "complete": item.complete,
            }
            for item in bundle.datasets
        ]
        payload: dict[str, object] = {
            "analysis_plan": analysis_plan.model_dump(mode="json"),
            "dataset_schemas": dataset_schemas,
            "feature_summaries": [item.model_dump(mode="json") for item in feature_summaries],
            "metric_definitions": [
                {
                    "metric_id": item.metric_id,
                    "version": item.version,
                    "display_name": item.display_name,
                    "business_definition": item.business_definition,
                    "unit": item.unit,
                    "minimum_denominator": item.minimum_denominator,
                }
                for item in metric_definitions
            ],
            "data_qa": [item.model_dump(mode="json") for item in bundle.data_qa],
            "visualization_intents": [
                item.model_dump(mode="json") for item in visualization_definitions
            ],
            "dashboard_budget": {"max_blocks": analysis_plan.budget.max_blocks},
            "selector_grammar": (
                "first | argmax:<column> | argmin:<column> | where:<column>=<value>"
            ),
        }
        if fixture_id is not None:
            payload["fixture_id"] = fixture_id
        return await self.runtime.llm.generate(
            operation="post_query_insight_dashboard",
            system_prompt=self.runtime.system_prompt,
            input_payload=redact_secrets(payload),
            output_schema=InsightDashboardDraft,
            timeout_seconds=self.runtime.timeout_seconds,
            correlation_id=correlation_id,
        )

    async def repair(
        self,
        *,
        draft: InsightDashboardDraft,
        errors: tuple[str, ...],
        analysis_plan: AnalysisPlan,
        bundle: DatasetBundle,
        attempt: int,
        correlation_id: str,
        fixture_id: str | None = None,
    ) -> InsightDashboardDraft:
        payload = build_insight_dashboard_repair_payload(
            draft=draft,
            errors=errors,
            bundle=bundle,
            immutable_analysis_plan_hash=analysis_plan.content_hash,
            required_task_ids=tuple(
                item.task_id for item in analysis_plan.tasks if item.priority == "required"
            ),
            attempt=attempt,
            fixture_id=fixture_id,
        )
        return await self.runtime.llm.generate(
            operation="json_repair",
            system_prompt=self.runtime.system_prompt,
            input_payload=redact_secrets(payload),
            output_schema=InsightDashboardDraft,
            timeout_seconds=self.runtime.timeout_seconds,
            correlation_id=correlation_id,
        )
