"""Checked-in flat-row fixtures rendered into each compiled aggregation contract."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.contracts.execution import RawSearchResult, ShardSummary
from app.contracts.query import BucketPathItem, CompiledQuery
from app.gateway.mock import MockOpenSearchGateway


class FixtureBackedMockOpenSearchGateway(MockOpenSearchGateway):
    def __init__(self, fixture_path: Path) -> None:
        super().__init__()
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        rows = raw.get("rows") if isinstance(raw, dict) else None
        if not isinstance(rows, list) or not all(isinstance(item, dict) for item in rows):
            raise ValueError("Mock Gateway fixture must contain an object row array")
        self.rows: tuple[dict[str, Any], ...] = tuple(rows)
        self.fixture_id = str(raw.get("fixture_id", fixture_path.stem))

    async def execute_search(self, query: CompiledQuery) -> RawSearchResult:
        if not self.is_registered(query.query_fingerprint):
            self.register(query.query_fingerprint, self._render(query))
        result = await super().execute_search(query)
        return (
            result
            if result.query_id == query.object_id
            else result.model_copy(update={"query_id": query.object_id})
        )

    def _render(self, query: CompiledQuery) -> RawSearchResult:
        scoped_rows = self._scoped_rows(query)
        bucket_path = query.semantics.bucket_path
        aggregations: dict[str, Any]
        if not bucket_path:
            aggregations = {"doc_count": sum(self._count(item) for item in scoped_rows)}
        elif bucket_path[0].bucket_kind == "composite":
            aggregations = self._composite(bucket_path, scoped_rows)
        else:
            aggregations = self._nested(bucket_path, 0, scoped_rows)
        return RawSearchResult(
            query_id=query.object_id,
            took_ms=1,
            timed_out=False,
            shards=ShardSummary(total=1, successful=1, skipped=0, failed=0),
            aggregations=aggregations,
            raw_size_bytes=len(json.dumps(aggregations, ensure_ascii=False).encode("utf-8")),
            gateway_metadata={"fixture_id": self.fixture_id},
        )

    def _nested(
        self,
        path: tuple[BucketPathItem, ...],
        level: int,
        rows: tuple[dict[str, Any], ...],
    ) -> dict[str, Any]:
        spec = path[level]
        groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            key = row.get(spec.dimension_id)
            if spec.bucket_kind == "date_histogram" and "month" in spec.aggregation_name:
                key = self._month_key(key)
            groups[key].append(row)
        buckets: list[dict[str, Any]] = []
        for key in sorted(groups, key=lambda item: (item is None, str(item))):
            grouped_rows = tuple(groups[key])
            bucket: dict[str, Any] = {
                "key": key,
                "doc_count": sum(self._count(item) for item in grouped_rows),
            }
            if spec.bucket_kind == "date_histogram" and key is not None:
                bucket["key_as_string"] = str(key)
            if level + 1 < len(path):
                bucket.update(self._nested(path, level + 1, grouped_rows))
            buckets.append(bucket)
        return {
            spec.aggregation_name: {
                "doc_count_error_upper_bound": 0,
                "sum_other_doc_count": 0,
                "buckets": buckets,
            }
        }

    def _composite(
        self, path: tuple[BucketPathItem, ...], rows: tuple[dict[str, Any], ...]
    ) -> dict[str, Any]:
        root = path[0].key_field
        if root is None or any(item.key_field != root for item in path):
            raise ValueError("composite fixture requires one shared root")
        groups: dict[tuple[Any, ...], int] = defaultdict(int)
        for row in rows:
            key = tuple(
                self._month_key(row.get(item.dimension_id))
                if "month" in item.aggregation_name
                else row.get(item.dimension_id)
                for item in path
            )
            groups[key] += self._count(row)
        buckets = [
            {
                "key": {
                    item.aggregation_name: value for item, value in zip(path, key, strict=True)
                },
                "doc_count": count,
            }
            for key, count in sorted(groups.items(), key=lambda item: repr(item[0]))
        ]
        return {root: {"buckets": buckets}}

    def _scoped_rows(self, query: CompiledQuery) -> tuple[dict[str, Any], ...]:
        start = query.semantics.time_range.from_inclusive
        end = query.semantics.time_range.to_exclusive
        rows = tuple(
            row
            for row in self.rows
            if isinstance(row.get(query.semantics.time_field_id), str)
            and start <= datetime.fromisoformat(str(row[query.semantics.time_field_id])) < end
        )
        query_body = query.query_dsl.get("query")
        bool_body = query_body.get("bool") if isinstance(query_body, dict) else None
        filters = bool_body.get("filter", ()) if isinstance(bool_body, dict) else ()
        if not isinstance(filters, list):
            return rows
        for clause in filters[1:]:
            if not isinstance(clause, dict):
                continue
            if isinstance(clause.get("term"), dict):
                field, value = next(iter(clause["term"].items()))
                rows = tuple(row for row in rows if self._field_value(row, field) == value)
            elif isinstance(clause.get("terms"), dict):
                field, values = next(iter(clause["terms"].items()))
                rows = tuple(row for row in rows if self._field_value(row, field) in set(values))
            elif isinstance(clause.get("bool"), dict):
                must_not = clause["bool"].get("must_not", ())
                if isinstance(must_not, list):
                    for excluded in must_not:
                        rows = self._exclude(rows, excluded)
        return rows

    @staticmethod
    def _exclude(rows: tuple[dict[str, Any], ...], clause: object) -> tuple[dict[str, Any], ...]:
        if not isinstance(clause, dict):
            return rows
        body = clause.get("term") or clause.get("terms")
        if not isinstance(body, dict):
            return rows
        field, value = next(iter(body.items()))
        excluded = set(value) if isinstance(value, list) else {value}
        return tuple(
            row
            for row in rows
            if FixtureBackedMockOpenSearchGateway._field_value(row, field) not in excluded
        )

    @staticmethod
    def _field_value(row: dict[str, Any], physical_path: object) -> object:
        leaf = str(physical_path).removesuffix(".keyword")
        match = next(
            (value for key, value in row.items() if key == leaf or key.endswith(f".{leaf}")),
            None,
        )
        return match

    @staticmethod
    def _month_key(value: object) -> object:
        if not isinstance(value, str):
            return value
        parsed = datetime.fromisoformat(value)
        return parsed.replace(month=parsed.month, day=1, hour=0, minute=0, second=0).isoformat()

    @staticmethod
    def _count(row: dict[str, Any]) -> int:
        value = row.get("record_count", 0)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError("fixture record_count must be a non-negative integer")
        return value
