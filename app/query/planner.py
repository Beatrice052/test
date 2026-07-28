from __future__ import annotations

from uuid import uuid4

from app.agent.contracts import (
    AnalysisPlan,
    AnalysisType,
    GroupBy,
    QueryFilter,
    QueryLimits,
    QueryPlan,
)
from app.query.index_resolver import MonthlyIndexResolver
from app.semantic.models import CompiledSemanticModel
from app.semantic.resolver import ResolutionResult


class QueryPlanBuilder:
    def __init__(self, model: CompiledSemanticModel) -> None:
        self.model = model
        self.index_resolver = MonthlyIndexResolver(model.policy)

    def build(
        self,
        analysis: AnalysisPlan,
        resolution: ResolutionResult,
        *,
        available_indices: set[str] | None = None,
    ) -> list[QueryPlan]:
        index_resolution = self.index_resolver.resolve(
            analysis.time_range.from_,
            analysis.time_range.to,
            available_indices=available_indices,
        )
        if index_resolution.missing_indices:
            raise ValueError(
                "indices not available: " + ", ".join(index_resolution.missing_indices)
            )

        filters: list[QueryFilter] = []
        for item in analysis.filter_concepts:
            if item.operator == "eq":
                operator = "term"
            elif item.operator == "in":
                operator = "terms"
            else:
                operator = "range"
            filters.append(
                QueryFilter(
                    field=resolution.field_resolution[f"filter:{item.concept}"],
                    operator=operator,
                    values=item.values,
                )
            )
        group_by: list[GroupBy] = []
        for concept in analysis.dimension_concepts:
            if concept == "date":
                group_by.append(
                    GroupBy(
                        kind="date_histogram",
                        field=resolution.field_resolution["date"],
                        interval=analysis.time_range.grain or "day",
                    )
                )
            else:
                group_by.append(
                    GroupBy(
                        kind="terms",
                        field=resolution.field_resolution[concept],
                        size=10 if analysis.analysis_type == AnalysisType.TOP_N else 20,
                    )
                )

        primary = QueryPlan(
            query_id=f"q-{uuid4()}",
            dataset_id="sub_message",
            physical_indices=index_resolution.indices,
            query_type=analysis.analysis_type,
            time_filter={
                "field": resolution.field_resolution["event_time"],
                "from": analysis.time_range.from_.isoformat(),
                "to": analysis.time_range.to.isoformat(),
                "time_zone": self.model.dataset.business_timezone,
            },
            filters=filters,
            group_by=group_by,
            metric_refs=list(resolution.metric_resolution),
            independent_tasks=1,
            limits=QueryLimits(
                max_buckets=self.model.policy.max_buckets,
                timeout_seconds=self.model.policy.timeout_seconds,
                max_top_n=self.model.policy.max_top_n,
            ),
        )
        plans = [primary]

        additional = (analysis.comparison or {}).get("additional_analysis")
        if additional:
            dimension = str(additional["dimension"])
            plans.append(
                primary.model_copy(
                    update={
                        "query_id": f"q-{uuid4()}",
                        "query_type": AnalysisType(additional["query_type"]),
                        "group_by": [
                            GroupBy(
                                kind="terms",
                                field=resolution.field_resolution[dimension],
                                size=int(additional.get("size", 10)),
                            )
                        ],
                        "independent_tasks": 2,
                    },
                    deep=True,
                )
            )
            plans[0] = plans[0].model_copy(update={"independent_tasks": 2}, deep=True)
        return plans
