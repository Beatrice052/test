"""Deterministic data quality rules and FATAL insight admission control."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime

from app.contracts.common import TimeRange
from app.contracts.dataset import (
    DataQARecord,
    DatasetCompleteness,
    DatasetContract,
    ReconciliationRecord,
    TabularDataset,
)
from app.contracts.execution import ExecutionRecord
from app.contracts.metric import MetricValue


class DataQAEngine:
    def evaluate(
        self,
        dataset: TabularDataset,
        *,
        contract: DatasetContract | None = None,
        executions: Sequence[ExecutionRecord] = (),
        metric_values_by_row: Mapping[str, tuple[MetricValue, ...]] | None = None,
        reconciliation: Sequence[ReconciliationRecord] = (),
        time_range: TimeRange | None = None,
        mapping_compatible: bool = True,
        rederived_content_hash: str | None = None,
    ) -> tuple[DataQARecord, ...]:
        records: list[DataQARecord] = []
        records.extend(self._execution_rules(dataset, executions))
        expected_dimensions = contract.dimensions if contract is not None else dataset.grain
        column_names = {item.name for item in dataset.columns}
        missing_dimensions = tuple(item for item in expected_dimensions if item not in column_names)
        records.append(
            self._record(
                "qa_dimension_present",
                "FATAL",
                not missing_dimensions,
                dataset,
                "all required dimensions are present"
                if not missing_dimensions
                else f"missing dimensions: {','.join(missing_dimensions)}",
            )
        )
        duplicate_ids = tuple(
            row_id
            for row_id, count in Counter(row.row_id for row in dataset.rows).items()
            if count > 1
        )
        records.append(
            self._record(
                "qa_unique_primary_key",
                "FATAL",
                not duplicate_ids,
                dataset,
                "row IDs are unique" if not duplicate_ids else "duplicate row IDs found",
                evidence_row_ids=duplicate_ids,
            )
        )
        records.append(self._completeness_rule(dataset))
        records.append(
            self._record(
                "qa_mapping_compatibility",
                "FATAL",
                mapping_compatible,
                dataset,
                "mapping is compatible"
                if mapping_compatible
                else "multi-index mapping is incompatible",
            )
        )
        if time_range is not None:
            records.append(self._time_rule(dataset, time_range))
        values = metric_values_by_row or {}
        records.extend(self._metric_rules(dataset, values))
        for item in reconciliation:
            records.append(
                self._record(
                    "qa_total_reconcile",
                    "ERROR",
                    item.passed,
                    dataset,
                    item.message,
                    details={
                        "reconciliation_id": item.reconciliation_id,
                        "expected": item.expected,
                        "actual": item.actual,
                    },
                )
            )
        if dataset.kind == "derived":
            reproducible = (
                rederived_content_hash is not None
                and rederived_content_hash == dataset.content_hash
            )
            records.append(
                self._record(
                    "qa_derived_reproducible",
                    "ERROR",
                    reproducible,
                    dataset,
                    "derived content hash reproduced"
                    if reproducible
                    else "derived content hash was not reproduced",
                )
            )
        return tuple(records)

    @staticmethod
    def has_fatal(records: Sequence[DataQARecord]) -> bool:
        return any(item.severity == "FATAL" and not item.passed for item in records)

    @staticmethod
    def has_blocking(records: Sequence[DataQARecord]) -> bool:
        """ERROR/FATAL data is retained for audit but cannot enter Agent C."""

        return any(item.severity in {"ERROR", "FATAL"} and not item.passed for item in records)

    def _execution_rules(
        self, dataset: TabularDataset, executions: Sequence[ExecutionRecord]
    ) -> list[DataQARecord]:
        failed_shards = sum(item.shard_failures for item in executions)
        timed_out = any(item.timed_out for item in executions)
        return [
            self._record(
                "qa_shard_failure",
                "FATAL",
                failed_shards == 0,
                dataset,
                "no shard failures" if failed_shards == 0 else f"{failed_shards} shards failed",
                details={"failed_shards": failed_shards},
            ),
            self._record(
                "qa_timeout",
                "ERROR",
                not timed_out,
                dataset,
                "query completed within timeout" if not timed_out else "query timed out",
            ),
        ]

    def _completeness_rule(self, dataset: TabularDataset) -> DataQARecord:
        passed = dataset.completeness in {
            DatasetCompleteness.COMPLETE,
            DatasetCompleteness.TOP_N_WITH_OTHERS,
        }
        return self._record(
            "qa_terms_completeness",
            "ERROR",
            passed,
            dataset,
            f"bucket completeness is {dataset.completeness.value}",
        )

    def _time_rule(self, dataset: TabularDataset, time_range: TimeRange) -> DataQARecord:
        time_columns = [item.name for item in dataset.columns if item.data_type == "datetime"]
        invalid: list[str] = []
        for row in dataset.rows:
            for column in time_columns:
                value = row.values.get(column)
                try:
                    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                except ValueError:
                    invalid.append(row.row_id)
                    continue
                if not time_range.from_inclusive <= parsed < time_range.to_exclusive:
                    invalid.append(row.row_id)
        return self._record(
            "qa_time_range",
            "FATAL",
            not invalid,
            dataset,
            "all time buckets are in range" if not invalid else "time bucket is out of range",
            evidence_row_ids=tuple(dict.fromkeys(invalid)),
        )

    def _metric_rules(
        self,
        dataset: TabularDataset,
        values_by_row: Mapping[str, tuple[MetricValue, ...]],
    ) -> list[DataQARecord]:
        ratio_invalid: list[str] = []
        numerator_invalid: list[str] = []
        unknown_rows: list[str] = []
        small_rows: list[str] = []
        for row_id, values in values_by_row.items():
            for value in values:
                if value.unit == "ratio" and value.value is not None and not 0 <= value.value <= 1:
                    ratio_invalid.append(row_id)
                if (
                    value.numerator is not None
                    and value.denominator is not None
                    and value.numerator > value.denominator
                ):
                    numerator_invalid.append(row_id)
                if value.excluded.get("unknown", 0) + value.excluded.get("null", 0) > 0:
                    unknown_rows.append(row_id)
                if value.quality == "INSUFFICIENT_SAMPLE":
                    small_rows.append(row_id)
        return [
            self._record(
                "qa_ratio_bounds",
                "FATAL",
                not ratio_invalid,
                dataset,
                "all ratios are within [0,1]" if not ratio_invalid else "ratio is out of bounds",
                evidence_row_ids=tuple(dict.fromkeys(ratio_invalid)),
            ),
            self._record(
                "qa_numerator_le_denominator",
                "FATAL",
                not numerator_invalid,
                dataset,
                "all numerators are at most their denominators"
                if not numerator_invalid
                else "numerator exceeds denominator",
                evidence_row_ids=tuple(dict.fromkeys(numerator_invalid)),
            ),
            self._record(
                "qa_unknown_status",
                "WARNING",
                not unknown_rows,
                dataset,
                "no unknown or null statuses"
                if not unknown_rows
                else "unknown or null statuses were excluded",
                evidence_row_ids=tuple(dict.fromkeys(unknown_rows)),
            ),
            self._record(
                "qa_small_sample",
                "WARNING",
                not small_rows,
                dataset,
                "all metric samples meet minimum size"
                if not small_rows
                else "one or more metric samples are below minimum size",
                evidence_row_ids=tuple(dict.fromkeys(small_rows)),
            ),
        ]

    @staticmethod
    def _record(
        rule_id: str,
        severity: str,
        passed: bool,
        dataset: TabularDataset,
        message: str,
        *,
        evidence_row_ids: tuple[str, ...] = (),
        details: dict[str, object] | None = None,
    ) -> DataQARecord:
        return DataQARecord.model_validate(
            {
                "rule_id": rule_id,
                "severity": severity,
                "passed": passed,
                "message": message,
                "dataset_id": dataset.dataset_id,
                "evidence_row_ids": evidence_row_ids,
                "details": details or {},
            },
            strict=False,
        )
