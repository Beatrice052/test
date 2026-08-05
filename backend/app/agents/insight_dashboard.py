"""Agent C proposes grounded claim selectors and visualization intent, never numbers or code."""

from __future__ import annotations

from app.agents.base import AgentRuntime
from app.contracts.analysis import AnalysisPlan
from app.contracts.dashboard import (
    VisualizationDefinition,
    VisualizationExplorationDraft,
    VisualizationPreview,
)
from app.contracts.dataset import DatasetBundle
from app.contracts.insight import AnalyticsToolResult, FeatureSummary, InsightDashboardDraft
from app.contracts.metric import MethodDefinition, MetricDefinition
from app.llm.redaction import redact_secrets
from app.llm.repair import build_insight_dashboard_repair_payload


class InsightDashboardAgent:
    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime

    async def explore(
        self,
        *,
        analysis_plan: AnalysisPlan,
        bundle: DatasetBundle,
        feature_summaries: tuple[FeatureSummary, ...],
        metric_definitions: tuple[MetricDefinition, ...],
        method_definitions: tuple[MethodDefinition, ...],
        visualization_definitions: tuple[VisualizationDefinition, ...],
        correlation_id: str,
        fixture_id: str | None = None,
    ) -> VisualizationExplorationDraft:
        payload = self._input_payload(
            analysis_plan=analysis_plan,
            bundle=bundle,
            feature_summaries=feature_summaries,
            metric_definitions=metric_definitions,
            method_definitions=method_definitions,
            visualization_definitions=visualization_definitions,
        )
        payload["stage"] = "propose_bounded_visual_exploration"
        if fixture_id is not None:
            payload["fixture_id"] = fixture_id
        return await self.runtime.llm.generate(
            operation="post_query_visual_exploration",
            system_prompt=self.runtime.system_prompt,
            input_payload=redact_secrets(payload),
            output_schema=VisualizationExplorationDraft,
            timeout_seconds=self.runtime.timeout_seconds,
            correlation_id=correlation_id,
        )

    async def plan(
        self,
        *,
        analysis_plan: AnalysisPlan,
        bundle: DatasetBundle,
        feature_summaries: tuple[FeatureSummary, ...],
        metric_definitions: tuple[MetricDefinition, ...],
        method_definitions: tuple[MethodDefinition, ...],
        visualization_definitions: tuple[VisualizationDefinition, ...],
        visualization_previews: tuple[VisualizationPreview, ...],
        analytics_tool_results: tuple[AnalyticsToolResult, ...] = (),
        correlation_id: str,
        fixture_id: str | None = None,
    ) -> InsightDashboardDraft:
        payload = self._input_payload(
            analysis_plan=analysis_plan,
            bundle=bundle,
            feature_summaries=feature_summaries,
            metric_definitions=metric_definitions,
            method_definitions=method_definitions,
            visualization_definitions=visualization_definitions,
        )
        payload["stage"] = "synthesize_insights_from_validated_visual_previews"
        payload["visualization_previews"] = [
            item.model_dump(mode="json") for item in visualization_previews
        ]
        payload["analytics_tool_results"] = [
            item.model_dump(mode="json") for item in analytics_tool_results
        ]
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

    @staticmethod
    def _input_payload(
        *,
        analysis_plan: AnalysisPlan,
        bundle: DatasetBundle,
        feature_summaries: tuple[FeatureSummary, ...],
        metric_definitions: tuple[MetricDefinition, ...],
        method_definitions: tuple[MethodDefinition, ...],
        visualization_definitions: tuple[VisualizationDefinition, ...],
    ) -> dict[str, object]:
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
        dataset_tables = [
            {
                "dataset_id": item.dataset_id,
                "table_id": item.object_id,
                "kind": item.kind,
                "grain": list(item.grain),
                "columns": [column.name for column in item.columns],
                "rows": [row.model_dump(mode="json") for row in item.rows[:500]],
                "row_count": len(item.rows),
                "rows_complete_in_payload": len(item.rows) <= 500,
                "completeness": item.completeness,
                "content_hash": item.content_hash,
            }
            for item in bundle.datasets
        ]
        failed_qa = [item for item in bundle.data_qa if not item.passed]
        return {
            "analysis_plan": analysis_plan.model_dump(mode="json"),
            "dataset_schemas": dataset_schemas,
            "validated_dataset_tables": dataset_tables,
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
            "governed_analysis_tools": {
                "statistical_analysis": {
                    "request_contract": {
                        "dataset_id": "one supplied dataset_id",
                        "measure_column": "one supplied numeric metric/measure column",
                        "method_id": "one registered method_id",
                        "parameters": "only registered default parameter names",
                        "partition_columns": "zero or more supplied dimension columns",
                        "category_column": "optional supplied category dimension",
                        "time_column": "optional supplied time dimension",
                    },
                    "methods": [
                        {
                            "method_id": item.method_id,
                            "version": item.version,
                            "display_name": item.display_name,
                            "minimum_rows": item.minimum_rows,
                            "required_semantic_types": item.required_semantic_types,
                            "default_params": item.default_params,
                            "parameter_limits": item.parameter_limits,
                            "requires_category": item.requires_category,
                            "requires_time": item.requires_time,
                        }
                        for item in method_definitions
                    ],
                }
            },
            "data_quality": {
                "status": (
                    "BLOCKED"
                    if any(item.severity in {"ERROR", "FATAL"} for item in failed_qa)
                    else "WARNING"
                    if failed_qa or bundle.warnings
                    else "VALID"
                ),
                "material_warnings": [item.message for item in failed_qa],
                "completeness": [
                    {
                        "dataset_id": item.dataset_id,
                        "status": item.completeness,
                        "complete": item.complete,
                    }
                    for item in bundle.datasets
                ],
            },
            "visualization_intents": [
                item.model_dump(mode="json") for item in visualization_definitions
            ],
            "dashboard_budget": {"max_blocks": analysis_plan.budget.max_blocks},
            "selector_grammar": (
                "first | argmax:<column> | argmin:<column> | where:<column>=<value> | "
                "statistic:<method_id>@<source_column> with "
                "binding.column=<scalar value path>"
            ),
        }

    async def repair(
        self,
        *,
        draft: InsightDashboardDraft,
        errors: tuple[str, ...],
        analysis_plan: AnalysisPlan,
        bundle: DatasetBundle,
        feature_summaries: tuple[FeatureSummary, ...],
        visualization_previews: tuple[VisualizationPreview, ...],
        attempt: int,
        correlation_id: str,
        fixture_id: str | None = None,
    ) -> InsightDashboardDraft:
        payload = build_insight_dashboard_repair_payload(
            draft=draft,
            errors=errors,
            bundle=bundle,
            feature_summaries=feature_summaries,
            immutable_analysis_plan_hash=analysis_plan.content_hash,
            required_task_ids=tuple(
                item.task_id for item in analysis_plan.tasks if item.priority == "required"
            ),
            preview_ids=tuple(item.object_id for item in visualization_previews),
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
