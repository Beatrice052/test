"""Bounded host-side statistical tools selected by Agent C after data retrieval.

The LLM decides which useful questions to ask of the validated data.  This module
does the arithmetic and applicability checks, records an immutable result, and
never accepts model-authored code, formulas, raw queries, or renderer options.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.analytics.statistics import StatisticEngine
from app.contracts.analysis import AnalysisPlan
from app.contracts.common import Provenance, semantic_hash
from app.contracts.dataset import DatasetBundle, TabularDataset
from app.contracts.insight import (
    AnalyticsToolRequest,
    AnalyticsToolResult,
    FeatureSummary,
    StatisticalResult,
)
from app.contracts.metric import MethodDefinition
from app.persistence.ids import new_id


@dataclass(frozen=True, slots=True)
class AnalyticsToolExecution:
    results: tuple[AnalyticsToolResult, ...]
    feature_summaries: tuple[FeatureSummary, ...]
    warnings: tuple[str, ...]


class GovernedAnalyticsTool:
    """Execute only registered statistics over exact post-query Dataset columns."""

    def __init__(self, method_definitions: tuple[MethodDefinition, ...]) -> None:
        self.methods = {item.method_id: item for item in method_definitions}
        self.engine = StatisticEngine()

    def execute(
        self,
        requests: tuple[AnalyticsToolRequest, ...],
        *,
        analysis_plan: AnalysisPlan,
        bundle: DatasetBundle,
        feature_summaries: tuple[FeatureSummary, ...],
    ) -> AnalyticsToolExecution:
        request_ids = tuple(item.request_id for item in requests)
        if len(set(request_ids)) != len(request_ids):
            raise ValueError("analytics tool request IDs are not unique")
        known_task_ids = {item.task_id for item in analysis_plan.tasks}
        datasets = {item.dataset_id: item for item in bundle.datasets}
        blocked_datasets = {
            item.dataset_id
            for item in bundle.data_qa
            if item.dataset_id is not None
            and item.severity in {"ERROR", "FATAL"}
            and not item.passed
        }
        results = tuple(
            self._execute_one(
                request,
                known_task_ids=known_task_ids,
                datasets=datasets,
                blocked_datasets=blocked_datasets,
            )
            for request in requests
        )
        enriched = self._merge_feature_summaries(feature_summaries, results)
        warnings = tuple(result.reason for result in results if result.decision != "APPLICABLE")
        return AnalyticsToolExecution(
            results=results,
            feature_summaries=enriched,
            warnings=warnings,
        )

    def _execute_one(
        self,
        request: AnalyticsToolRequest,
        *,
        known_task_ids: set[str],
        datasets: dict[str, TabularDataset],
        blocked_datasets: set[str],
    ) -> AnalyticsToolResult:
        dataset = datasets.get(request.dataset_id)
        definition = self.methods.get(request.method_id)
        error: str | None = None
        if set(request.task_ids) - known_task_ids:
            error = "request references an unknown analytical task"
        elif dataset is None:
            error = "request references an unavailable dataset"
        elif request.dataset_id in blocked_datasets:
            error = "dataset is blocked by ERROR/FATAL data quality checks"
        elif definition is None:
            error = "request references an unregistered statistical method"
        elif not any(
            item.name == request.measure_column
            and item.semantic_role in {"metric", "measure"}
            and item.data_type in {"integer", "number", "metric"}
            for item in dataset.columns
        ):
            error = "measure column is missing or is not a governed numeric measure"
        elif set(request.parameters) - set(definition.default_params):
            error = "request overrides a statistical parameter that is not registered"

        if error is None:
            assert dataset is not None
            assert definition is not None
            missing = self._missing_capabilities(definition, dataset)
            if missing:
                error = "registered method capability is unavailable: " + ",".join(missing)

        if error is not None:
            result = StatisticalResult(
                method_id=request.method_id,
                version="unavailable" if definition is None else definition.version,
                applicability="NOT_APPLICABLE",
                sample_size=0,
                values={"column": request.measure_column},
                warnings=(error,),
            )
            return self._result(request, result, "REJECTED", error, dataset)

        assert dataset is not None
        assert definition is not None
        parameters = {
            **definition.default_params,
            **request.parameters,
            "column": request.measure_column,
        }
        time_column = next(
            (
                item.name
                for item in dataset.columns
                if item.data_type == "datetime" or item.semantic_type == "time_dimension"
            ),
            None,
        )
        if time_column is not None:
            parameters.setdefault("time_column", time_column)
        result = self.engine.compute(request.method_id, dataset, parameters)
        if result.applicability == "APPLICABLE" and result.sample_size < definition.minimum_rows:
            result = result.model_copy(
                update={
                    "applicability": "NOT_APPLICABLE",
                    "warnings": tuple(
                        dict.fromkeys(
                            [
                                *result.warnings,
                                "registered minimum_rows was not satisfied",
                            ]
                        )
                    ),
                }
            )
        decision = "APPLICABLE" if result.applicability == "APPLICABLE" else "NOT_APPLICABLE"
        reason = "registered method executed over the requested validated measure"
        if decision != "APPLICABLE":
            reason = "; ".join(result.warnings) or "registered method is not applicable"
        return self._result(request, result, decision, reason, dataset)

    @staticmethod
    def _missing_capabilities(
        definition: MethodDefinition,
        dataset: TabularDataset,
    ) -> tuple[str, ...]:
        available = {"numeric_measure"}
        if any(
            item.data_type == "datetime" or item.semantic_type == "time_dimension"
            for item in dataset.columns
        ):
            available.add("time_dimension")
        if any(
            item.semantic_role == "dimension"
            and item.data_type != "datetime"
            and item.semantic_type != "time_dimension"
            for item in dataset.columns
        ):
            available.add("categorical_dimension")
        return tuple(
            requirement
            for requirement in definition.required_semantic_types
            if requirement not in available
        )

    @staticmethod
    def _result(
        request: AnalyticsToolRequest,
        result: StatisticalResult,
        decision: str,
        reason: str,
        dataset: TabularDataset | None,
    ) -> AnalyticsToolResult:
        payload = {
            "request": request.model_dump(mode="json"),
            "decision": decision,
            "result": result.model_dump(mode="json"),
            "reason": reason,
        }
        return AnalyticsToolResult(
            object_id=new_id("atr"),
            created_at=datetime.now(UTC),
            content_hash=semantic_hash(payload),
            provenance=Provenance(
                producer="analytics.governed_tool",
                source_ids=() if dataset is None else (dataset.object_id,),
            ),
            request_id=request.request_id,
            task_ids=request.task_ids,
            dataset_id=request.dataset_id,
            method_id=request.method_id,
            measure_column=request.measure_column,
            decision=decision,
            result=result,
            reason=reason,
        )

    @staticmethod
    def _merge_feature_summaries(
        summaries: tuple[FeatureSummary, ...],
        results: tuple[AnalyticsToolResult, ...],
    ) -> tuple[FeatureSummary, ...]:
        by_dataset: dict[str, list[StatisticalResult]] = {}
        for result in results:
            if result.decision == "REJECTED":
                continue
            by_dataset.setdefault(result.dataset_id, []).append(result.result)
        merged: list[FeatureSummary] = []
        for summary in summaries:
            additions = by_dataset.get(summary.dataset_id, [])
            if not additions:
                merged.append(summary)
                continue
            existing = {
                (item.method_id, str(item.values.get("column", "")))
                for item in summary.statistical_results
            }
            selected = tuple(
                item
                for item in additions
                if (item.method_id, str(item.values.get("column", ""))) not in existing
            )
            merged.append(
                summary.model_copy(
                    update={"statistical_results": (*summary.statistical_results, *selected)}
                )
            )
        return tuple(merged)
