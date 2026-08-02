"""Semantic reconciliation and read-only DSL allowlist validation."""

from __future__ import annotations

from typing import Any, cast

from app.contracts.query import CompiledQuery, QueryPlan
from app.contracts.semantic import CanonicalField, PolicyDefinition


class QueryValidationError(ValueError):
    pass


class CompiledQueryValidator:
    FORBIDDEN_KEYS = frozenset(
        {
            "script",
            "script_fields",
            "runtime_mappings",
            "update",
            "delete",
            "painless",
        }
    )
    ALLOWED_TOP_LEVEL = frozenset({"size", "track_total_hits", "query", "aggs"})

    def __init__(
        self,
        *,
        fields: tuple[CanonicalField, ...],
        policies: tuple[PolicyDefinition, ...],
    ) -> None:
        self.fields = {item.field_id: item for item in fields}
        self.allowed_indices = {
            index for policy in policies for index in policy.allowed_index_patterns
        }

    def validate(self, query: CompiledQuery, plan: QueryPlan) -> None:
        step = next((item for item in plan.steps if item.step_id == query.step_id), None)
        if step is None:
            raise QueryValidationError("compiled query step is absent from QueryPlan")
        if query.query_plan_id != plan.object_id:
            raise QueryValidationError("compiled query references another QueryPlan")
        if query.indices != step.index_patterns or not set(query.indices).issubset(
            self.allowed_indices
        ):
            raise QueryValidationError("compiled indices differ from routed allowlist")
        dsl = query.query_dsl
        if dsl.get("size") != 0:
            raise QueryValidationError("aggregation query must use size=0")
        if set(dsl) - self.ALLOWED_TOP_LEVEL:
            raise QueryValidationError("DSL has an unapproved top-level clause")
        forbidden = self._find_keys(dsl).intersection(self.FORBIDDEN_KEYS)
        if forbidden:
            raise QueryValidationError(f"DSL has forbidden clauses: {sorted(forbidden)}")
        allowed_paths = {
            self.fields[field_id].physical_path
            for field_id in query.semantics.field_ids
            if field_id in self.fields
        }
        physical_paths = self._physical_paths(dsl)
        if not physical_paths.issubset(allowed_paths):
            raise QueryValidationError(
                f"DSL uses unresolved physical fields: {sorted(physical_paths - allowed_paths)}"
            )
        time_path = self.fields[step.time_field_id].physical_path
        time_clause = self._find_range(dsl, time_path)
        if time_clause is None:
            raise QueryValidationError("DSL dropped the required time filter")
        if time_clause.get("gte") != step.time_range.from_inclusive.isoformat() or (
            time_clause.get("lt") != step.time_range.to_exclusive.isoformat()
        ):
            raise QueryValidationError("DSL time filter differs from QueryPlan")

    @classmethod
    def _find_keys(cls, value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value).union(*(cls._find_keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(cls._find_keys(item) for item in value)) if value else set()
        return set()

    @classmethod
    def _physical_paths(cls, value: Any) -> set[str]:
        paths: set[str] = set()
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"term", "terms", "range"} and isinstance(child, dict):
                    if isinstance(child.get("field"), str):
                        paths.add(str(child["field"]))
                    else:
                        paths.update(str(field) for field in child)
                elif key == "exists" and isinstance(child, dict) and "field" in child:
                    paths.add(str(child["field"]))
                elif key == "field" and isinstance(child, str):
                    paths.add(child)
                paths.update(cls._physical_paths(child))
        elif isinstance(value, list):
            for child in value:
                paths.update(cls._physical_paths(child))
        return paths

    @classmethod
    def _find_range(cls, value: Any, field: str) -> dict[str, Any] | None:
        if isinstance(value, dict):
            range_body = value.get("range")
            if isinstance(range_body, dict) and isinstance(range_body.get(field), dict):
                return cast(dict[str, Any], range_body[field])
            for child in value.values():
                found = cls._find_range(child, field)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = cls._find_range(child, field)
                if found is not None:
                    return found
        return None
