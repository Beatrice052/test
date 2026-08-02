"""Recursively flatten governed OpenSearch buckets into a stable tabular dataset."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.analytics.identity import stable_row_id
from app.analytics.parser import ParsedSearchResult
from app.contracts.common import JsonValue, Provenance, semantic_hash
from app.contracts.dataset import (
    DatasetCompleteness,
    DatasetContract,
    DatasetRow,
    TabularDataset,
)
from app.contracts.query import BucketPathItem


class DatasetContractViolation(ValueError):
    pass


class ResultNormalizer:
    """Use only DatasetContract bucket paths; never infer business grain from raw JSON."""

    def normalize(
        self,
        parsed: ParsedSearchResult,
        contract: DatasetContract,
    ) -> TabularDataset:
        if contract.object_id != parsed.query.result_contract_id:
            raise DatasetContractViolation("dataset contract does not match compiled query")
        rows: list[DatasetRow] = []
        observations = _CompletenessObservations()
        if contract.bucket_path:
            self._walk(
                level=0,
                node=parsed.raw.aggregations,
                dimensions={},
                rows=rows,
                contract=contract,
                observations=observations,
            )
        else:
            rows.append(
                self._build_row(
                    contract,
                    {},
                    self._record_count(parsed.raw.aggregations),
                    self._metric_values(parsed.raw.aggregations),
                )
            )
        row_ids = [row.row_id for row in rows]
        if len(row_ids) != len(set(row_ids)):
            raise DatasetContractViolation("normalized primary key is not unique")
        for row in rows:
            missing = [name for name in contract.dimensions if name not in row.values]
            if missing:
                raise DatasetContractViolation(
                    f"required contract dimensions are missing: {sorted(missing)}"
                )
        completeness = observations.classify(parsed.raw.gateway_metadata)
        warnings = tuple(observations.warnings)
        payload = {
            "dataset_id": contract.dataset_id,
            "contract_id": contract.object_id,
            "kind": "base",
            "grain": contract.grain,
            "columns": [item.model_dump(mode="json") for item in contract.columns],
            "rows": [item.model_dump(mode="json") for item in rows],
            "completeness": completeness,
            "warnings": warnings,
        }
        content_hash = semantic_hash(payload)
        return TabularDataset(
            object_id=f"ds_{contract.dataset_id}_{content_hash[7:15]}",
            created_at=datetime.now(UTC),
            content_hash=content_hash,
            provenance=Provenance(
                producer="analytics.result_normalizer",
                source_ids=(parsed.query.object_id, contract.object_id),
                source_hashes={"raw_result": semantic_hash(parsed.raw)},
            ),
            dataset_id=contract.dataset_id,
            contract_id=contract.object_id,
            kind="base",
            grain=contract.grain,
            columns=contract.columns,
            rows=tuple(rows),
            completeness=completeness,
            complete=completeness
            in {DatasetCompleteness.COMPLETE, DatasetCompleteness.TOP_N_WITH_OTHERS},
            truncated=completeness == DatasetCompleteness.TRUNCATED,
            warnings=warnings,
        )

    def _walk(
        self,
        *,
        level: int,
        node: Mapping[str, Any],
        dimensions: dict[str, JsonValue],
        rows: list[DatasetRow],
        contract: DatasetContract,
        observations: _CompletenessObservations,
    ) -> None:
        if level == len(contract.bucket_path):
            rows.append(
                self._build_row(
                    contract,
                    dimensions,
                    self._record_count(node),
                    self._metric_values(node),
                )
            )
            return
        spec = contract.bucket_path[level]
        if spec.bucket_kind == "composite" and spec.key_field is not None:
            composite_specs: list[BucketPathItem] = []
            cursor = level
            while cursor < len(contract.bucket_path):
                candidate = contract.bucket_path[cursor]
                if candidate.bucket_kind != "composite" or candidate.key_field != spec.key_field:
                    break
                composite_specs.append(candidate)
                cursor += 1
            container = self._require_aggregation(node, spec.key_field)
            observations.observe(container)
            for bucket_key, bucket in self._bucket_items(container):
                expanded = {
                    **dimensions,
                    **{
                        item.dimension_id: self._decode_bucket_key(bucket_key, bucket, item)
                        for item in composite_specs
                    },
                }
                self._walk(
                    level=cursor,
                    node=bucket,
                    dimensions=expanded,
                    rows=rows,
                    contract=contract,
                    observations=observations,
                )
            return
        container_name = (
            spec.key_field
            if spec.bucket_kind == "composite" and spec.key_field is not None
            else spec.aggregation_name
        )
        container = self._require_aggregation(node, container_name)
        observations.observe(container)
        for bucket_key, bucket in self._bucket_items(container):
            value = self._decode_bucket_key(bucket_key, bucket, spec)
            self._walk(
                level=level + 1,
                node=bucket,
                dimensions={**dimensions, spec.dimension_id: value},
                rows=rows,
                contract=contract,
                observations=observations,
            )

    @classmethod
    def _require_aggregation(
        cls, node: Mapping[str, Any], aggregation_name: str
    ) -> Mapping[str, Any]:
        candidate = node.get(aggregation_name)
        if isinstance(candidate, Mapping):
            return candidate
        for value in node.values():
            if isinstance(value, Mapping) and cls._is_wrapper(value):
                found = cls._find_named_aggregation(value, aggregation_name)
                if found is not None:
                    return found
        raise DatasetContractViolation(f"required aggregation is missing: {aggregation_name}")

    @classmethod
    def _find_named_aggregation(
        cls, node: Mapping[str, Any], aggregation_name: str
    ) -> Mapping[str, Any] | None:
        candidate = node.get(aggregation_name)
        if isinstance(candidate, Mapping):
            return candidate
        for value in node.values():
            if isinstance(value, Mapping) and cls._is_wrapper(value):
                found = cls._find_named_aggregation(value, aggregation_name)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _is_wrapper(value: Mapping[str, Any]) -> bool:
        return "doc_count" in value and "buckets" not in value

    @staticmethod
    def _bucket_items(
        container: Mapping[str, Any],
    ) -> tuple[tuple[str | None, Mapping[str, Any]], ...]:
        buckets = container.get("buckets")
        if isinstance(buckets, list):
            if not all(isinstance(item, Mapping) for item in buckets):
                raise DatasetContractViolation("bucket array contains a non-object item")
            return tuple((None, item) for item in buckets)
        if isinstance(buckets, Mapping):
            if not all(isinstance(item, Mapping) for item in buckets.values()):
                raise DatasetContractViolation("keyed buckets contain a non-object item")
            return tuple((str(key), item) for key, item in buckets.items())
        raise DatasetContractViolation("aggregation buckets are missing or malformed")

    @staticmethod
    def _decode_bucket_key(
        keyed_name: str | None,
        bucket: Mapping[str, Any],
        spec: BucketPathItem,
    ) -> JsonValue:
        key = bucket.get("key")
        if spec.bucket_kind == "composite":
            if not isinstance(key, Mapping) or spec.aggregation_name not in key:
                raise DatasetContractViolation("composite bucket key does not match contract")
            return ResultNormalizer._json_scalar(key[spec.aggregation_name])
        if spec.bucket_kind == "date_histogram" and "key_as_string" in bucket:
            return str(bucket["key_as_string"])
        if key is not None:
            return ResultNormalizer._json_scalar(key)
        if keyed_name is not None:
            return keyed_name
        return None

    @staticmethod
    def _json_scalar(value: Any) -> JsonValue:
        if isinstance(value, str | int | float | bool) or value is None:
            return value
        raise DatasetContractViolation("bucket key is not a JSON scalar")

    @staticmethod
    def _record_count(node: Mapping[str, Any]) -> int:
        value = node.get("doc_count", 0)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise DatasetContractViolation("bucket doc_count is invalid")
        return value

    @classmethod
    def _build_row(
        cls,
        contract: DatasetContract,
        dimensions: Mapping[str, JsonValue],
        record_count: int,
        raw_metrics: Mapping[str, JsonValue],
    ) -> DatasetRow:
        values: dict[str, JsonValue] = {**dimensions, "record_count": record_count}
        if raw_metrics:
            values["raw_metrics"] = dict(raw_metrics)
        return DatasetRow(
            row_id=stable_row_id(contract.dataset_id, contract.primary_key, dimensions),
            values=values,
        )

    @staticmethod
    def _metric_values(node: Mapping[str, Any]) -> dict[str, JsonValue]:
        values: dict[str, JsonValue] = {}
        for name, child in node.items():
            if not isinstance(child, Mapping) or "value" not in child:
                continue
            value = child.get("value")
            if isinstance(value, str | int | float | bool) or value is None:
                values[name] = value
        return values


class _CompletenessObservations:
    def __init__(self) -> None:
        self.truncated = False
        self.after_key = False
        self.has_others = False
        self.warnings: list[str] = []

    def observe(self, container: Mapping[str, Any]) -> None:
        other = container.get("sum_other_doc_count", 0)
        error = container.get("doc_count_error_upper_bound", 0)
        if isinstance(other, int) and other > 0:
            self.truncated = True
            self.warnings.append(f"terms omitted {other} documents")
        if isinstance(error, int) and error > 0:
            self.truncated = True
            self.warnings.append(f"terms doc_count error upper bound is {error}")
        if container.get("after_key") is not None:
            self.after_key = True
            self.warnings.append("composite result has a next page")
        buckets = container.get("buckets")
        keys: list[Any] = []
        if isinstance(buckets, Mapping):
            keys.extend(buckets)
        elif isinstance(buckets, list):
            keys.extend(item.get("key") for item in buckets if isinstance(item, Mapping))
        self.has_others = self.has_others or any(
            str(key).casefold() in {"others", "other", "__other__"} for key in keys
        )

    def classify(self, metadata: Mapping[str, JsonValue]) -> DatasetCompleteness:
        if self.after_key and metadata.get("composite_complete") is not True:
            return DatasetCompleteness.PARTIAL
        if self.truncated and self.has_others:
            return DatasetCompleteness.TOP_N_WITH_OTHERS
        if self.truncated:
            return DatasetCompleteness.TRUNCATED
        if metadata.get("partial") is True:
            return DatasetCompleteness.PARTIAL
        return DatasetCompleteness.COMPLETE
