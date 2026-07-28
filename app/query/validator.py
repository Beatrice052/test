from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.query.models import (
    CompiledQuery,
    ValidationCheck,
    ValidationResult,
)
from app.semantic.models import CompiledSemanticModel, FieldAccess


class QueryValidationError(ValueError):
    def __init__(self, result: ValidationResult) -> None:
        self.result = result
        failed = [check.name for check in result.checks if not check.passed]
        super().__init__("query validation failed: " + ", ".join(failed))


class QueryDslValidator:
    FORBIDDEN_KEYS = {"script", "script_fields", "runtime_mappings"}

    def __init__(self, model: CompiledSemanticModel) -> None:
        self.model = model
        self.fields = model.field_map()
        pattern = re.escape(model.policy.index_pattern)
        pattern = pattern.replace(re.escape("{yyyy}"), r"\d{4}")
        pattern = pattern.replace(re.escape("{mm}"), r"(0[1-9]|1[0-2])")
        self.index_regex = re.compile(f"^{pattern}$")

    def validate(self, query: CompiledQuery) -> tuple[CompiledQuery, ValidationResult]:
        referenced_fields = self._referenced_fields(query.body)
        checks = [
            ValidationCheck(
                name="read_only",
                passed=query.read_only and self.model.policy.read_only,
            ),
            ValidationCheck(
                name="index_allowlist",
                passed=bool(self.index_regex.fullmatch(query.index)),
            ),
            ValidationCheck(
                name="forbidden_dsl",
                passed=not bool(self._all_keys(query.body) & self.FORBIDDEN_KEYS),
            ),
            ValidationCheck(
                name="field_exists",
                passed=all(self._field_allowed(field) for field in referenced_fields),
                detail=", ".join(sorted(referenced_fields)),
            ),
            ValidationCheck(
                name="bucket_limit",
                passed=self._bucket_sizes_within_limit(query.body),
            ),
            ValidationCheck(
                name="time_range",
                passed=self._time_range_within_limit(query.body),
            ),
            ValidationCheck(
                name="response_size",
                passed=query.body.get("size", 0) <= self.model.policy.max_detail_size,
            ),
        ]
        status = "PASSED" if all(check.passed for check in checks) else "FAILED"
        result = ValidationResult(
            status=status,
            checks=checks,
            estimated_complexity=query.estimated_complexity,
        )
        if status == "FAILED":
            raise QueryValidationError(result)
        return query.model_copy(update={"validation_status": "PASSED"}), result

    def _field_allowed(self, field_path: str) -> bool:
        direct = self.fields.get(field_path)
        if direct is not None:
            return direct.access is FieldAccess.ALLOWED
        if field_path.endswith(".keyword"):
            parent = self.fields.get(field_path.removesuffix(".keyword"))
            return (
                parent is not None
                and parent.access is FieldAccess.ALLOWED
                and parent.physical_aggregation_path == field_path
            )
        return False

    def _time_range_within_limit(self, body: dict[str, Any]) -> bool:
        for node in self._walk(body):
            if "range" not in node or not isinstance(node["range"], dict):
                continue
            for definition in node["range"].values():
                if not isinstance(definition, dict) or "gte" not in definition:
                    continue
                start = datetime.fromisoformat(str(definition["gte"]))
                end = datetime.fromisoformat(str(definition["lt"]))
                if (end - start).days > self.model.policy.max_time_range_days:
                    return False
        return True

    def _bucket_sizes_within_limit(self, body: dict[str, Any]) -> bool:
        for node in self._walk(body):
            terms = node.get("terms")
            if isinstance(terms, dict):
                size = int(terms.get("size", 10))
                if size > min(self.model.policy.max_top_n, self.model.policy.max_buckets):
                    return False
        return True

    @classmethod
    def _referenced_fields(cls, body: dict[str, Any]) -> set[str]:
        fields: set[str] = set()
        for node in cls._walk(body):
            for key in ("term", "terms", "range"):
                value = node.get(key)
                if isinstance(value, dict):
                    if "field" in value:
                        fields.add(str(value["field"]))
                    else:
                        fields.update(str(field) for field in value)
            histogram = node.get("date_histogram")
            if isinstance(histogram, dict) and "field" in histogram:
                fields.add(str(histogram["field"]))
        return fields

    @classmethod
    def _all_keys(cls, body: dict[str, Any]) -> set[str]:
        keys: set[str] = set()
        for node in cls._walk(body):
            keys.update(node)
        return keys

    @classmethod
    def _walk(cls, value: Any):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from cls._walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from cls._walk(child)
