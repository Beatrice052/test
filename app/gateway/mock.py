from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.gateway.execution import execute_queries, plan_execution
from app.gateway.models import (
    ExecutionBundle,
    ExecutionStep,
    GatewayCapabilities,
    GatewayFault,
)
from app.query.models import CompiledQuery


def normalize_status(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip().upper()


class MockOpenSearchGateway:
    def __init__(
        self,
        data_dir: Path,
        mapping_path: Path,
        *,
        fault: GatewayFault = GatewayFault.NONE,
        capabilities: GatewayCapabilities | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.mapping_path = mapping_path
        self.fault = fault
        self._capabilities = capabilities or GatewayCapabilities()
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def capabilities(self) -> GatewayCapabilities:
        return self._capabilities.model_copy(deep=True)

    def list_indices(self, pattern: str | None = None) -> list[str]:
        indices = sorted(path.stem for path in self.data_dir.glob("*.jsonl"))
        if pattern is None:
            return indices
        prefix = pattern.split("*", 1)[0]
        return [index for index in indices if index.startswith(prefix)]

    def get_mapping(self, index: str) -> dict[str, Any]:
        if index not in self.list_indices():
            raise KeyError(f"index not found: {index}")
        return json.loads(self.mapping_path.read_text(encoding="utf-8"))

    def count(self, index: str, query: dict[str, Any]) -> dict[str, Any]:
        records = self._filtered_records(index, query)
        payload = self._base_payload(len(records))
        payload["count"] = len(records)
        return payload

    def search(self, index: str, body: dict[str, Any]) -> dict[str, Any]:
        records = self._filtered_records(index, body)
        payload = self._base_payload(len(records))
        payload["hits"] = {"total": {"value": len(records), "relation": "eq"}, "hits": []}
        aggregations = body.get("aggs", {})
        if aggregations:
            payload["aggregations"] = self._execute_aggregations(records, aggregations)
        if self.fault is GatewayFault.BUCKET_TRUNCATED:
            payload["_meta"]["truncated"] = True
        if self.fault is GatewayFault.METRIC_QA_FAILED:
            self._corrupt_metric_counts(payload)
        return payload

    def msearch(self, requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.search(item["index"], item["body"]) for item in requests]

    def plan_execution(self, queries: list[CompiledQuery]) -> list[ExecutionStep]:
        return plan_execution(queries, self._capabilities)

    def execute(self, queries: list[CompiledQuery]) -> ExecutionBundle:
        return execute_queries(self, queries, self._capabilities)

    def _records(self, index: str) -> list[dict[str, Any]]:
        if index in self._cache:
            return self._cache[index]
        path = self.data_dir / f"{index}.jsonl"
        if not path.exists():
            raise KeyError(f"index not found: {index}")
        records = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self._cache[index] = records
        return records

    def _filtered_records(self, index: str, body: dict[str, Any]) -> list[dict[str, Any]]:
        records = [] if self.fault is GatewayFault.NO_DATA else self._records(index)
        filters = body.get("query", {}).get("bool", {}).get("filter", [])
        return [record for record in records if self._matches_all(record, filters)]

    def _base_payload(self, total: int) -> dict[str, Any]:
        return {
            "took": 1,
            "timed_out": self.fault is GatewayFault.QUERY_TIMEOUT,
            "_shards": {
                "total": 1,
                "successful": 0 if self.fault is GatewayFault.SHARD_FAILURE else 1,
                "skipped": 0,
                "failed": 1 if self.fault is GatewayFault.SHARD_FAILURE else 0,
            },
            "_meta": {"truncated": False, "synthetic": True, "matched": total},
        }

    def _execute_aggregations(
        self, records: list[dict[str, Any]], aggregations: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            name: self._execute_aggregation(records, definition)
            for name, definition in aggregations.items()
        }

    def _execute_aggregation(
        self, records: list[dict[str, Any]], definition: dict[str, Any]
    ) -> dict[str, Any]:
        if "filter" in definition:
            matched = [
                record for record in records if self._matches_clause(record, definition["filter"])
            ]
            result: dict[str, Any] = {"doc_count": len(matched)}
            if "aggs" in definition:
                result.update(self._execute_aggregations(matched, definition["aggs"]))
            return result
        if "terms" in definition:
            terms = definition["terms"]
            field = terms["field"]
            missing = terms.get("missing", "__NULL__")
            groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for record in records:
                value = self._field_value(record, field)
                key = missing if value is None else str(value)
                groups[key].append(record)
            ordered = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
            buckets = []
            for key, group_records in ordered[: int(terms.get("size", 10))]:
                bucket: dict[str, Any] = {"key": key, "doc_count": len(group_records)}
                if "aggs" in definition:
                    bucket.update(self._execute_aggregations(group_records, definition["aggs"]))
                buckets.append(bucket)
            return {
                "doc_count_error_upper_bound": 0,
                "sum_other_doc_count": sum(
                    len(group) for _, group in ordered[int(terms.get("size", 10)) :]
                ),
                "buckets": buckets,
            }
        if "date_histogram" in definition:
            histogram = definition["date_histogram"]
            field = histogram["field"]
            start = datetime.fromisoformat(histogram["extended_bounds"]["min"])
            end = datetime.fromisoformat(histogram["extended_bounds"]["max"])
            groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for record in records:
                value = self._field_value(record, field)
                if value is not None:
                    groups[datetime.fromisoformat(str(value)).date().isoformat()].append(record)
            buckets = []
            cursor = start
            while cursor < end:
                key = cursor.date().isoformat()
                group_records = groups.get(key, [])
                bucket: dict[str, Any] = {
                    "key_as_string": cursor.isoformat(),
                    "key": int(cursor.timestamp() * 1000),
                    "doc_count": len(group_records),
                }
                if "aggs" in definition:
                    bucket.update(self._execute_aggregations(group_records, definition["aggs"]))
                buckets.append(bucket)
                cursor += timedelta(days=1)
            return {"buckets": buckets}
        raise ValueError(f"unsupported aggregation: {definition}")

    def _matches_all(self, record: dict[str, Any], clauses: list[dict[str, Any]]) -> bool:
        return all(self._matches_clause(record, clause) for clause in clauses)

    def _matches_clause(self, record: dict[str, Any], clause: dict[str, Any]) -> bool:
        if "term" in clause:
            field, expected = next(iter(clause["term"].items()))
            return self._comparable(field, self._field_value(record, field)) == self._comparable(
                field, expected
            )
        if "terms" in clause:
            field, expected_values = next(iter(clause["terms"].items()))
            actual = self._comparable(field, self._field_value(record, field))
            expected = {self._comparable(field, value) for value in expected_values}
            return actual in expected
        if "range" in clause:
            field, bounds = next(iter(clause["range"].items()))
            value = self._field_value(record, field)
            if value is None:
                return False
            if field == "createdTime":
                actual = datetime.fromisoformat(str(value))
                lower = datetime.fromisoformat(str(bounds["gte"]))
                upper = datetime.fromisoformat(str(bounds["lt"]))
                return lower <= actual < upper
            numeric_actual = float(value)
            numeric_lower = float(bounds["gte"])
            numeric_upper = float(bounds["lt"])
            return numeric_lower <= numeric_actual < numeric_upper
        if "bool" in clause:
            return self._matches_all(record, clause["bool"].get("filter", []))
        raise ValueError(f"unsupported filter clause: {clause}")

    @staticmethod
    def _field_value(record: dict[str, Any], field: str) -> Any:
        field = field.removesuffix(".keyword")
        current: Any = record
        for part in field.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    @staticmethod
    def _comparable(field: str, value: Any) -> Any:
        return normalize_status(value) if field in {"status", "Status"} else value

    @staticmethod
    def _corrupt_metric_counts(payload: dict[str, Any]) -> None:
        aggregations = payload.get("aggregations", {})
        if "success" in aggregations and "failed" in aggregations:
            aggregations["success"]["doc_count"] = payload["hits"]["total"]["value"] + 1
            return
        group = aggregations.get("primary_group", {})
        buckets = group.get("buckets", [])
        for bucket in buckets:
            bucket["success"]["doc_count"] = bucket["doc_count"] + 1
