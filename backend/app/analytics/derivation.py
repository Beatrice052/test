"""Registered, reproducible derivations from base status buckets to governed metrics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from app.analytics.identity import stable_row_id
from app.analytics.metric_engine import MetricEngine
from app.contracts.common import JsonValue, Provenance, semantic_hash
from app.contracts.dataset import (
    DatasetColumn,
    DatasetRow,
    ReconciliationRecord,
    TabularDataset,
)
from app.contracts.metric import MetricDefinition, MetricValue, ValueDictionary


class DerivationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DerivationResult:
    dataset: TabularDataset
    metric_values_by_row: dict[str, tuple[MetricValue, ...]]
    reconciliation: tuple[ReconciliationRecord, ...]


@dataclass(slots=True)
class _Accumulator:
    counts: dict[str, int]
    row_ids: list[str]
    total: int = 0

    @classmethod
    def create(cls) -> _Accumulator:
        return cls(counts=defaultdict(int), row_ids=[])


class StatusMetricDeriver:
    IMPLEMENTATION_VERSION = "1.0"

    def __init__(self, metric_engine: MetricEngine | None = None) -> None:
        self.metric_engine = metric_engine or MetricEngine()

    def derive(
        self,
        source: TabularDataset,
        *,
        output_dataset_id: str,
        derivation_id: str,
        group_by: tuple[str, ...],
        status_field_id: str | None,
        value_dictionary: ValueDictionary,
        metric_definitions: tuple[MetricDefinition, ...],
    ) -> DerivationResult:
        if source.kind != "base":
            raise DerivationError("status metric derivation requires a base dataset")
        required = {*group_by, "record_count"}
        if status_field_id is not None:
            required.add(status_field_id)
        source_columns = {item.name for item in source.columns}
        if not required.issubset(source_columns):
            raise DerivationError(
                f"source dataset lacks required columns: {sorted(required - source_columns)}"
            )
        grouped: dict[tuple[JsonValue, ...], _Accumulator] = defaultdict(_Accumulator.create)
        for row in source.rows:
            raw_count = row.values.get("record_count")
            if not isinstance(raw_count, int) or isinstance(raw_count, bool) or raw_count < 0:
                raise DerivationError("source record_count is invalid")
            key = tuple(row.values.get(field) for field in group_by)
            accumulator = grouped[key]
            if status_field_id is not None:
                raw_status = row.values.get(status_field_id)
                status_group = self._status_group(raw_status, value_dictionary)
                accumulator.counts[status_group] = (
                    accumulator.counts.get(status_group, 0) + raw_count
                )
            accumulator.total += raw_count
            accumulator.row_ids.append(row.row_id)

        dimension_columns = tuple(
            column.model_copy(update={"nullable": True})
            for field in group_by
            for column in source.columns
            if column.name == field
        )
        if len(dimension_columns) != len(group_by):
            raise DerivationError("group_by columns are not uniquely represented")
        measure_columns = (
            DatasetColumn(
                name="record_count",
                data_type="integer",
                nullable=False,
                semantic_role="measure",
                unit="count",
            ),
        )
        metric_columns = tuple(
            DatasetColumn(
                name=definition.versioned_id,
                data_type="metric",
                nullable=True,
                semantic_role="metric",
                metric_id=definition.metric_id,
                unit=definition.unit,
            )
            for definition in metric_definitions
        )
        metadata_columns = (
            DatasetColumn(
                name="metric_metadata",
                data_type="metric",
                nullable=False,
                semantic_role="metadata",
            ),
        )
        rows: list[DatasetRow] = []
        metric_values_by_row: dict[str, tuple[MetricValue, ...]] = {}
        for key in sorted(grouped, key=lambda item: semantic_hash(item)):
            accumulator = grouped[key]
            counts = dict(accumulator.counts)
            evidence_row_ids = tuple(accumulator.row_ids)
            record_count = accumulator.total
            values: dict[str, JsonValue] = dict(zip(group_by, key, strict=True))
            metrics = tuple(
                self.metric_engine.compute(
                    definition,
                    record_count=record_count,
                    status_counts=counts,
                    evidence_row_ids=evidence_row_ids,
                )
                for definition in metric_definitions
            )
            values["record_count"] = record_count
            values.update(
                {
                    definition.versioned_id: value.value
                    for definition, value in zip(metric_definitions, metrics, strict=True)
                }
            )
            values["metric_metadata"] = {
                value.metric_id: value.model_dump(mode="json") for value in metrics
            }
            row_id = stable_row_id(output_dataset_id, group_by, values)
            rows.append(DatasetRow(row_id=row_id, values=values))
            metric_values_by_row[row_id] = metrics

        columns = (
            *dimension_columns,
            *measure_columns,
            *metric_columns,
            *metadata_columns,
        )
        derivation_metadata: dict[str, JsonValue] = {
            "derivation_id": derivation_id,
            "implementation_version": self.IMPLEMENTATION_VERSION,
            "source_dataset_ids": [source.dataset_id],
            "required_grain": list(source.grain),
            "required_columns": sorted(required),
            "output_grain": list(group_by),
            "output_columns": [item.name for item in columns],
            "formula_references": [item.versioned_id for item in metric_definitions],
            "reconciliation_rules": ["derived_record_count_equals_source_record_count"],
        }
        payload = {
            **derivation_metadata,
            "dataset_id": output_dataset_id,
            "rows": [item.model_dump(mode="json") for item in rows],
            "source_hash": source.content_hash,
        }
        content_hash = semantic_hash(payload)
        dataset = TabularDataset(
            object_id=f"ds_{output_dataset_id}_{content_hash[7:15]}",
            created_at=datetime.now(UTC),
            content_hash=content_hash,
            provenance=Provenance(
                producer="analytics.status_metric_deriver",
                source_ids=(source.object_id,),
                source_hashes={source.dataset_id: source.content_hash},
                metadata=derivation_metadata,
            ),
            dataset_id=output_dataset_id,
            contract_id=f"dc_{output_dataset_id}",
            kind="derived",
            grain=group_by,
            columns=columns,
            rows=tuple(rows),
            completeness=source.completeness,
            complete=source.complete,
            truncated=source.truncated,
            source_dataset_ids=(source.dataset_id,),
            derivation_id=derivation_id,
            warnings=source.warnings,
        )
        expected = 0
        for row in source.rows:
            raw_count = row.values.get("record_count")
            if isinstance(raw_count, int) and not isinstance(raw_count, bool):
                expected += raw_count
        actual = 0
        for row in rows:
            raw_count = row.values.get("record_count")
            if isinstance(raw_count, int) and not isinstance(raw_count, bool):
                actual += raw_count
        reconciliation = ReconciliationRecord(
            reconciliation_id=f"reconcile_{derivation_id}",
            passed=expected == actual,
            expected=expected,
            actual=actual,
            message="derived message record count equals source record count",
            dataset_ids=(source.dataset_id, output_dataset_id),
        )
        return DerivationResult(dataset, metric_values_by_row, (reconciliation,))

    @staticmethod
    def _status_group(value: JsonValue, dictionary: ValueDictionary) -> str:
        if value is None:
            return "null"
        if not isinstance(value, str):
            return "unknown"
        return dictionary.values.get(value, dictionary.null_group)
