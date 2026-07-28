from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.agent.contracts import AnalysisType, QueryPlan
from app.gateway.models import RawQueryResult
from app.metrics.engine import MetricEngine
from app.results.models import ChartSpec, PreparedData, ProcessedResult
from app.results.qa import DataQA
from app.semantic.models import CompiledSemanticModel


class ResultProcessor:
    def __init__(self, model: CompiledSemanticModel) -> None:
        self.model = model
        self.metric_engine = MetricEngine()
        self.qa = DataQA()

    def process(self, plan: QueryPlan, results: list[RawQueryResult]) -> ProcessedResult:
        payloads = [result.payload for result in results]
        if plan.query_type in {AnalysisType.COUNT, AnalysisType.FILTERED_COUNT}:
            return self._count_result(plan, results, payloads)
        if plan.group_by:
            return self._grouped_result(plan, results, payloads)
        if plan.metric_refs:
            return self._metric_summary(plan, results, payloads)
        return self._count_result(plan, results, payloads)

    def _count_result(
        self,
        plan: QueryPlan,
        results: list[RawQueryResult],
        payloads: list[dict[str, Any]],
    ) -> ProcessedResult:
        total = sum(self._payload_total(result.payload) for result in results)
        quality = self.qa.evaluate(payloads, total_count=total)
        prepared = PreparedData(
            columns=[{"name": "total_count", "type": "integer"}],
            rows=[],
            totals={"total_count": total},
            quality=quality,
            provenance=self._provenance(plan, results),
        )
        return ProcessedResult(
            prepared_data=prepared,
            raw_result_summary={"total_count": total, "partition_count": len(results)},
        )

    def _metric_summary(
        self,
        plan: QueryPlan,
        results: list[RawQueryResult],
        payloads: list[dict[str, Any]],
    ) -> ProcessedResult:
        total = sum(self._payload_total(result.payload) for result in results)
        success = sum(
            int(result.payload.get("aggregations", {}).get("success", {}).get("doc_count", 0))
            for result in results
        )
        failed = sum(
            int(result.payload.get("aggregations", {}).get("failed", {}).get("doc_count", 0))
            for result in results
        )
        values = self.metric_engine.failure_rate(total, success, failed)
        quality = self.qa.evaluate(
            payloads,
            total_count=total,
            success_count=success,
            failed_count=failed,
            failure_rate=values.failure_rate,
        )
        totals = values.model_dump()
        prepared = PreparedData(
            columns=[
                {"name": "total_count", "type": "integer"},
                {"name": "total_success_count", "type": "integer"},
                {"name": "total_failed_count", "type": "integer"},
                {"name": "other_count", "type": "integer"},
                {"name": "failure_rate", "type": "number"},
            ],
            rows=[],
            totals=totals,
            quality=quality,
            provenance=self._provenance(plan, results),
        )
        return ProcessedResult(
            prepared_data=prepared,
            raw_result_summary={**totals, "partition_count": len(results)},
        )

    def _grouped_result(
        self,
        plan: QueryPlan,
        results: list[RawQueryResult],
        payloads: list[dict[str, Any]],
    ) -> ProcessedResult:
        group = plan.group_by[0]
        group_field = (
            "date" if group.kind == "date_histogram" else group.field.removesuffix(".keyword")
        )
        merged: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "success": 0, "failed": 0}
        )
        sum_other = 0
        for result in results:
            aggregation = result.payload.get("aggregations", {}).get("primary_group", {})
            sum_other += int(aggregation.get("sum_other_doc_count", 0))
            for bucket in aggregation.get("buckets", []):
                key = (
                    str(bucket.get("key_as_string", ""))[:10]
                    if group.kind == "date_histogram"
                    else str(bucket.get("key"))
                )
                merged[key]["total"] += int(bucket.get("doc_count", 0))
                merged[key]["success"] += int(bucket.get("success", {}).get("doc_count", 0))
                merged[key]["failed"] += int(bucket.get("failed", {}).get("doc_count", 0))

        rows: list[dict[str, Any]] = []
        has_metric = bool(plan.metric_refs)
        for key, counts in merged.items():
            row: dict[str, Any] = {group_field: key, "total_count": counts["total"]}
            if has_metric:
                metric = self.metric_engine.failure_rate(
                    counts["total"], counts["success"], counts["failed"]
                )
                row.update(metric.model_dump())
            rows.append(row)

        if group.kind == "date_histogram":
            rows.sort(key=lambda row: str(row[group_field]))
        else:
            rows.sort(key=lambda row: (-int(row["total_count"]), str(row[group_field])))

        total = sum(self._payload_total(result.payload) for result in results)
        success = sum(int(row.get("total_success_count", 0)) for row in rows)
        failed = sum(int(row.get("total_failed_count", 0)) for row in rows)
        totals: dict[str, Any] = {"total_count": total}
        failure_rate: float | None = None
        if has_metric:
            metric_totals = self.metric_engine.failure_rate(total, success, failed)
            totals = metric_totals.model_dump()
            failure_rate = metric_totals.failure_rate
        bucket_total = sum(int(row["total_count"]) for row in rows) + sum_other
        quality = self.qa.evaluate(
            payloads,
            total_count=total,
            success_count=success if has_metric else None,
            failed_count=failed if has_metric else None,
            bucket_total=bucket_total,
            failure_rate=failure_rate,
        )
        columns = [
            {"name": group_field, "type": "date" if group.kind == "date_histogram" else "string"},
            {"name": "total_count", "type": "integer"},
        ]
        if has_metric:
            columns.extend(
                [
                    {"name": "total_success_count", "type": "integer"},
                    {"name": "total_failed_count", "type": "integer"},
                    {"name": "other_count", "type": "integer"},
                    {"name": "failure_rate", "type": "number"},
                ]
            )
        y_field = "failure_rate" if has_metric else "total_count"
        chart = ChartSpec(
            type="line" if group.kind == "date_histogram" else "bar",
            title=self._chart_title(group_field, has_metric),
            x_field=group_field,
            y_field=y_field,
            data=rows,
        )
        prepared = PreparedData(
            columns=columns,
            rows=rows,
            totals=totals,
            quality=quality,
            provenance=self._provenance(plan, results),
        )
        warnings = ["BUCKETS_TRUNCATED"] if sum_other else []
        return ProcessedResult(
            prepared_data=prepared,
            chart=chart,
            warnings=warnings,
            raw_result_summary={
                "total_count": total,
                "bucket_count": len(rows),
                "sum_other_doc_count": sum_other,
                "partition_count": len(results),
            },
        )

    def _provenance(self, plan: QueryPlan, results: list[RawQueryResult]) -> dict[str, Any]:
        return {
            "query_ids": [result.query_id for result in results],
            "logical_query_id": plan.query_id,
            "indices": [result.index for result in results],
            "metric_versions": {
                metric_id: self.model.metric_map()[metric_id].version
                for metric_id in plan.metric_refs
            },
            "semantic_model_version": self.model.model_version,
        }

    @staticmethod
    def _payload_total(payload: dict[str, Any]) -> int:
        if "count" in payload:
            return int(payload["count"])
        return int(payload.get("hits", {}).get("total", {}).get("value", 0))

    @staticmethod
    def _chart_title(group_field: str, has_metric: bool) -> str:
        metric = "Failure Rate" if has_metric else "Record Count"
        return f"{metric} by {group_field}"
