from __future__ import annotations

from app.agent.contracts import AnalysisType, QueryPlan
from app.query.models import CompiledQuery, Complexity
from app.semantic.models import CompiledSemanticModel


class QueryDslBuilder:
    def __init__(self, model: CompiledSemanticModel) -> None:
        self.model = model

    def build(self, plan: QueryPlan) -> list[CompiledQuery]:
        return [
            CompiledQuery(
                query_id=f"{plan.query_id}:{index}",
                logical_query_id=plan.query_id,
                index=index,
                query_type=plan.query_type,
                body=self._body(plan),
                estimated_complexity=self._complexity(plan),
            )
            for index in plan.physical_indices
        ]

    def _body(self, plan: QueryPlan) -> dict:
        body: dict = {"query": {"bool": {"filter": self._filters(plan)}}}
        if plan.query_type in {AnalysisType.COUNT, AnalysisType.FILTERED_COUNT}:
            return body

        body["size"] = 0
        if plan.group_by:
            body["aggs"] = self._group_aggregation(plan)
        elif plan.metric_refs:
            body["aggs"] = self._metric_aggregations()
        return body

    def _filters(self, plan: QueryPlan) -> list[dict]:
        filters: list[dict] = [
            {
                "range": {
                    plan.time_filter["field"]: {
                        "gte": plan.time_filter["from"],
                        "lt": plan.time_filter["to"],
                        "time_zone": plan.time_filter["time_zone"],
                    }
                }
            }
        ]
        for item in plan.filters:
            if item.operator == "term":
                filters.append({"term": {item.field: item.values[0]}})
            elif item.operator == "terms":
                filters.append({"terms": {item.field: item.values}})
            elif item.operator == "range":
                filters.append({"range": {item.field: self._range_values(item.values)}})
        return filters

    def _group_aggregation(self, plan: QueryPlan) -> dict:
        group = plan.group_by[0]
        if group.kind == "terms":
            aggregation: dict = {
                "terms": {
                    "field": group.field,
                    "size": group.size or 20,
                    "missing": "__NULL__",
                }
            }
        else:
            aggregation = {
                "date_histogram": {
                    "field": group.field,
                    "calendar_interval": group.interval or "day",
                    "time_zone": plan.time_filter["time_zone"],
                    "min_doc_count": 0,
                    "extended_bounds": {
                        "min": plan.time_filter["from"],
                        "max": plan.time_filter["to"],
                    },
                }
            }
        if plan.metric_refs:
            aggregation["aggs"] = self._metric_aggregations()
        return {"primary_group": aggregation}

    def _metric_aggregations(self) -> dict:
        metric = self.model.metric_map()["failure_rate"]
        if metric.lifecycle_field is None:
            raise ValueError("failure_rate lifecycle field is not bound")
        return {
            "success": {"filter": {"terms": {metric.lifecycle_field: metric.success_values}}},
            "failed": {"filter": {"terms": {metric.lifecycle_field: metric.failed_values}}},
        }

    @staticmethod
    def _range_values(values: list) -> dict:
        if len(values) != 2:
            raise ValueError("range filter requires [gte, lt]")
        return {"gte": values[0], "lt": values[1]}

    @staticmethod
    def _complexity(plan: QueryPlan) -> Complexity:
        if plan.query_type in {AnalysisType.COUNT, AnalysisType.FILTERED_COUNT}:
            return Complexity.LOW
        if len(plan.group_by) <= 1:
            return Complexity.MEDIUM
        return Complexity.HIGH
