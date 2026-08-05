"""Compile a finalized logical QueryStep through a closed AST into read-only DSL."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, cast

from app.contracts.common import JsonValue, Provenance, semantic_hash
from app.contracts.metric import AggregationKind, MetricDefinition
from app.contracts.query import (
    BucketPathItem,
    CompiledQuery,
    QueryPlan,
    QuerySemantics,
    QueryStep,
)
from app.contracts.semantic import CanonicalField
from app.persistence.ids import new_id
from app.query.ast import BucketNode, FilterNode, MeasureNode, QueryAst
from app.query.fingerprint import query_fingerprint
from app.query.time_grain import TimeGrainError, resolve_calendar_interval


class QueryCompilationError(ValueError):
    pass


class DslCompiler:
    def __init__(
        self,
        *,
        fields: tuple[CanonicalField, ...],
        metrics: tuple[MetricDefinition, ...],
        terms_complete_threshold: int = 1000,
        composite_page_size: int = 500,
    ) -> None:
        self.fields = {item.field_id: item for item in fields}
        self.metrics = {item.versioned_id: item for item in metrics}
        self.terms_complete_threshold = terms_complete_threshold
        self.composite_page_size = composite_page_size

    def compile(self, plan: QueryPlan, step_id: str) -> CompiledQuery:
        step = next((item for item in plan.steps if item.step_id == step_id), None)
        if step is None:
            raise QueryCompilationError(f"query step not found: {step_id}")
        if step.depends_on and step.parameter_bindings:
            bound_parameters = {item.parameter for item in step.parameter_bindings}
            if any(
                item.parameter.removesuffix("_values")
                not in {field.field_id.rsplit(".", 1)[-1] for field in step.filters}
                for item in step.parameter_bindings
            ):
                del bound_parameters
                raise QueryCompilationError("dependent step must be bound before compilation")
        ast = self._build_ast(step)
        dsl, bucket_path = self._compile_ast(step, ast)
        metric_required_fields = tuple(
            field_id for metric_id in step.measures for field_id in self._required_fields(metric_id)
        )
        measure_required_fields = tuple(
            item.source_field_id for item in step.field_measures if item.source_field_id is not None
        )
        field_ids = tuple(
            dict.fromkeys(
                (
                    step.time_field_id,
                    *step.dimensions,
                    *(item.field_id for item in step.filters),
                    *metric_required_fields,
                    *measure_required_fields,
                )
            )
        )
        semantics = QuerySemantics(
            dataset_id=step.dataset_id,
            time_range=step.time_range,
            time_field_id=step.time_field_id,
            field_ids=field_ids,
            metric_ids=step.measures,
            field_measures=step.field_measures,
            filter_fingerprint=semantic_hash(
                [item.model_dump(mode="json") for item in step.filters]
            ),
            grain=step.grain,
            bucket_path=bucket_path,
        )
        fingerprint = query_fingerprint(
            indices=step.index_patterns,
            query_dsl=cast(dict[str, object], dsl),
            semantics=semantics,
        )
        payload = {
            "query_plan_id": plan.object_id,
            "step_id": step.step_id,
            "indices": step.index_patterns,
            "query_dsl": dsl,
            "semantics": semantics.model_dump(mode="json"),
            "query_fingerprint": fingerprint,
        }
        return CompiledQuery(
            object_id=new_id("qry"),
            created_at=datetime.now(UTC),
            content_hash=semantic_hash(payload),
            provenance=Provenance(
                producer="query.dsl_compiler",
                source_ids=(plan.object_id,),
            ),
            query_plan_id=plan.object_id,
            step_id=step.step_id,
            indices=step.index_patterns,
            query_dsl=dsl,
            semantics=semantics,
            query_fingerprint=fingerprint,
            timeout_ms=step.timeout_ms,
            result_contract_id=step.result_contract_id,
        )

    def compile_composite_page(
        self, query: CompiledQuery, *, after_key: dict[str, JsonValue]
    ) -> CompiledQuery:
        dsl = cast(dict[str, Any], query.model_copy(deep=True).query_dsl)
        aggs = dsl.get("aggs")
        if not isinstance(aggs, dict) or len(aggs) != 1:
            raise QueryCompilationError("query is not a single composite aggregation")
        aggregate = next(iter(aggs.values()))
        if not isinstance(aggregate, dict) or not isinstance(aggregate.get("composite"), dict):
            raise QueryCompilationError("query is not composite")
        aggregate["composite"]["after"] = after_key
        return query.model_copy(
            update={
                "query_dsl": dsl,
                "content_hash": semantic_hash(
                    {
                        "query_id": query.object_id,
                        "query_fingerprint": query.query_fingerprint,
                        "page_dsl": dsl,
                    }
                ),
            }
        )

    def _build_ast(self, step: QueryStep) -> QueryAst:
        filters = tuple(
            FilterNode(kind=item.operator, field_id=item.field_id, values=item.values)
            for item in step.filters
        )
        use_composite = step.estimated_buckets > self.terms_complete_threshold
        buckets: list[BucketNode] = []
        for index, field_id in enumerate(step.dimensions):
            field = self._field(field_id)
            leaf = field_id.rsplit(".", 1)[-1]
            if field_id == step.time_field_id:
                try:
                    interval = resolve_calendar_interval(step.grain)
                except TimeGrainError as error:
                    raise QueryCompilationError(str(error)) from error
                buckets.append(
                    BucketNode(
                        name=f"dim_{index:02d}_{interval}",
                        kind="composite" if use_composite else "date_histogram",
                        field_id=field_id,
                        interval=interval,
                        time_zone=step.time_range.timezone,
                    )
                )
            else:
                if "group_by" not in field.capabilities:
                    raise QueryCompilationError(f"field is not groupable: {field_id}")
                buckets.append(
                    BucketNode(
                        name=f"dim_{index:02d}_{leaf}",
                        kind="composite" if use_composite else "terms",
                        field_id=field_id,
                        size=min(max(step.estimated_buckets, 10), self.terms_complete_threshold),
                    )
                )
        measures = tuple(
            MeasureNode(
                name=f"metric_{index:02d}_{metric_id.split('.', 1)[0]}",
                kind="document_count",
                metric_id=metric_id,
            )
            for index, metric_id in enumerate(step.measures)
        ) + tuple(
            MeasureNode(
                name=specification.aggregation_name,
                kind=specification.aggregation.value,
                metric_id=specification.measure_id,
                field_id=specification.source_field_id,
                parameters=specification.parameters,
            )
            for specification in step.field_measures
        )
        return QueryAst(filters=filters, buckets=tuple(buckets), measures=measures)

    def _compile_ast(
        self, step: QueryStep, ast: QueryAst
    ) -> tuple[dict[str, JsonValue], tuple[BucketPathItem, ...]]:
        time_field = self._field(step.time_field_id).physical_path
        filters: list[dict[str, Any]] = [
            {
                "range": {
                    time_field: {
                        "gte": step.time_range.from_inclusive.isoformat(),
                        "lt": step.time_range.to_exclusive.isoformat(),
                    }
                }
            }
        ]
        filters.extend(self._compile_filter(node) for node in ast.filters)
        dsl: dict[str, Any] = {
            "size": 0,
            "track_total_hits": False,
            "query": {"bool": {"filter": filters}},
            "aggs": {},
        }
        bucket_path: list[BucketPathItem] = []
        if ast.buckets and all(node.kind == "composite" for node in ast.buckets):
            root_name = "composite_root"
            sources: list[dict[str, Any]] = []
            for node in ast.buckets:
                field = self._field(node.field_id).physical_path
                if node.interval is not None:
                    source = {
                        "date_histogram": {
                            "field": field,
                            "calendar_interval": node.interval,
                            "time_zone": node.time_zone,
                        }
                    }
                else:
                    source = {"terms": {"field": field}}
                sources.append({node.name: source})
                bucket_path.append(
                    BucketPathItem(
                        aggregation_name=node.name,
                        dimension_id=node.field_id,
                        bucket_kind="composite",
                        key_field=root_name,
                    )
                )
            root_body: dict[str, Any] = {
                "composite": {"size": self.composite_page_size, "sources": sources},
                "aggs": {},
            }
            dsl["aggs"] = {root_name: root_body}
            current_aggs = root_body["aggs"]
        else:
            current_aggs = dsl["aggs"]
            for node in ast.buckets:
                field = self._field(node.field_id).physical_path
                bucket_kind: Literal["date_histogram", "terms"]
                if node.kind == "date_histogram":
                    body: dict[str, Any] = {
                        "date_histogram": {
                            "field": field,
                            "calendar_interval": node.interval,
                            "time_zone": node.time_zone,
                            "min_doc_count": 0,
                        }
                    }
                    bucket_kind = "date_histogram"
                else:
                    body = {
                        "terms": {
                            "field": field,
                            "size": node.size,
                            "shard_size": min((node.size or 10) * 2, 10000),
                            "show_term_doc_count_error": True,
                        }
                    }
                    bucket_kind = "terms"
                current_aggs[node.name] = body
                bucket_path.append(
                    BucketPathItem(
                        aggregation_name=node.name,
                        dimension_id=node.field_id,
                        bucket_kind=bucket_kind,
                    )
                )
                body["aggs"] = {}
                current_aggs = body["aggs"]
        for measure in ast.measures:
            if measure.kind == "document_count":
                continue
            current_aggs[measure.name] = self._compile_measure(measure)
        return cast(dict[str, JsonValue], dsl), tuple(bucket_path)

    def _compile_measure(self, node: MeasureNode) -> dict[str, Any]:
        if node.field_id is None:
            raise QueryCompilationError(f"field aggregation lacks source field: {node.metric_id}")
        field = self._field(node.field_id)
        capability = f"aggregate_{node.kind}"
        if capability not in field.capabilities:
            raise QueryCompilationError(f"field does not support {node.kind}: {node.field_id}")
        body: dict[str, Any] = {"field": field.physical_path}
        if node.kind == AggregationKind.CARDINALITY.value:
            if node.parameters.precision_threshold is not None:
                body["precision_threshold"] = node.parameters.precision_threshold
        elif node.kind == AggregationKind.PERCENTILES.value:
            body["percents"] = list(node.parameters.percents or (50.0, 95.0, 99.0))
            body["keyed"] = node.parameters.keyed
        elif (
            node.kind == AggregationKind.EXTENDED_STATS.value and node.parameters.sigma is not None
        ):
            body["sigma"] = node.parameters.sigma
        return {node.kind: body}

    def _compile_filter(self, node: FilterNode) -> dict[str, Any]:
        field = self._field(node.field_id).physical_path
        if node.kind == "exists":
            return {"exists": {"field": field}}
        if node.kind == "range":
            if len(node.values) != 2:
                raise QueryCompilationError("range filter requires exactly two values")
            return {"range": {field: {"gte": node.values[0], "lt": node.values[1]}}}
        if node.kind == "eq":
            if len(node.values) != 1:
                raise QueryCompilationError("eq filter requires exactly one value")
            return {"term": {field: node.values[0]}}
        if node.kind == "in":
            if not node.values:
                raise QueryCompilationError("in filter cannot be empty")
            return {"terms": {field: list(node.values)}}
        if not node.values:
            raise QueryCompilationError("not filter cannot be empty")
        clause = (
            {"term": {field: node.values[0]}}
            if len(node.values) == 1
            else {"terms": {field: list(node.values)}}
        )
        return {"bool": {"must_not": [clause]}}

    def _field(self, field_id: str) -> CanonicalField:
        field = self.fields.get(field_id)
        if field is None:
            raise QueryCompilationError(f"unknown field_id: {field_id}")
        return field

    def _required_fields(self, metric_id: str) -> tuple[str, ...]:
        if metric_id not in self.metrics:
            raise QueryCompilationError(f"unknown metric_id: {metric_id}")
        return ()
