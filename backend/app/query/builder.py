"""Bind dependent-query values that came from a real prior result."""

from __future__ import annotations

from app.contracts.execution import RawSearchResult
from app.contracts.query import CompiledQuery, ParameterBinding, QueryFilter, QueryStep


class DependencyBindingError(ValueError):
    pass


class DependentQueryBinder:
    def values_from_result(
        self,
        binding: ParameterBinding,
        source_query: CompiledQuery,
        result: RawSearchResult,
    ) -> tuple[str | int | float | bool, ...]:
        target = binding.parameter.removesuffix("_values")
        bucket_item = next(
            (
                item
                for item in source_query.semantics.bucket_path
                if item.dimension_id.rsplit(".", 1)[-1] == target
            ),
            None,
        )
        if bucket_item is None:
            raise DependencyBindingError(f"source result has no dimension for {binding.parameter}")
        if bucket_item.bucket_kind == "composite":
            if bucket_item.key_field is None:
                raise DependencyBindingError("composite bucket path has no root aggregation")
            aggregate = result.aggregations.get(bucket_item.key_field)
            buckets = aggregate.get("buckets", ()) if isinstance(aggregate, dict) else ()
            scored = [
                (
                    bucket.get("key", {}).get(bucket_item.aggregation_name),
                    bucket.get("doc_count", 0),
                )
                for bucket in buckets
                if isinstance(bucket, dict) and isinstance(bucket.get("key"), dict)
            ]
        else:
            aggregate = result.aggregations.get(bucket_item.aggregation_name)
            buckets = aggregate.get("buckets", ()) if isinstance(aggregate, dict) else ()
            scored = [
                (bucket.get("key"), bucket.get("doc_count", 0))
                for bucket in buckets
                if isinstance(bucket, dict)
            ]
        values = [
            value
            for value, _ in sorted(scored, key=lambda item: (-float(item[1]), str(item[0])))
            if value is not None
        ]
        if binding.selection == "top_n":
            values = values[: binding.n or 1]
        elif binding.selection == "scalar":
            values = values[:1]
        return tuple(value for value in values if isinstance(value, str | int | float | bool))

    def bind(
        self,
        step: QueryStep,
        values_by_parameter: dict[str, tuple[str | int | float | bool, ...]],
    ) -> QueryStep:
        filters = list(step.filters)
        for binding in step.parameter_bindings:
            values = values_by_parameter.get(binding.parameter)
            if not values:
                raise DependencyBindingError(
                    f"dependent parameter has no values: {binding.parameter}"
                )
            target = binding.parameter.removesuffix("_values")
            candidates = [
                field_id for field_id in step.dimensions if field_id.rsplit(".", 1)[-1] == target
            ]
            if len(candidates) != 1:
                raise DependencyBindingError(
                    f"dependent parameter target is not unique: {binding.parameter}"
                )
            filters.append(QueryFilter(field_id=candidates[0], operator="in", values=values))
        return step.model_copy(update={"filters": tuple(filters)})
