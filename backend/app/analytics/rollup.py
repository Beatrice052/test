"""Deterministic additive rollups used by safe Dashboard views."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from app.analytics.identity import stable_row_id
from app.contracts.common import JsonValue, Provenance, semantic_hash
from app.contracts.dataset import (
    DatasetRow,
    ReconciliationRecord,
    TabularDataset,
)


class RollupDerivationError(ValueError):
    pass


class AdditiveRollupDeriver:
    """Sum the governed record_count measure at a declared subset grain."""

    IMPLEMENTATION_VERSION = "1.0"

    def derive(
        self,
        source: TabularDataset,
        *,
        output_dataset_id: str,
        group_by: tuple[str, ...],
        measure_columns: tuple[str, ...] = ("record_count",),
        task_ids: tuple[str, ...] = (),
    ) -> tuple[TabularDataset, ReconciliationRecord]:
        columns_by_name = {item.name: item for item in source.columns}
        required = {*measure_columns, *group_by}
        available = set(columns_by_name)
        if not required.issubset(available):
            raise RollupDerivationError(
                f"rollup source lacks columns: {sorted(required - available)}"
            )
        non_additive = tuple(
            name
            for name in measure_columns
            if columns_by_name[name].aggregation_semantics != "additive"
            and not (name == "record_count" and columns_by_name[name].aggregation_semantics is None)
        )
        if non_additive:
            raise RollupDerivationError(
                f"non-additive measures cannot be summed in a rollup: {sorted(non_additive)}"
            )
        grouped: dict[tuple[JsonValue, ...], dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        integral = {name: True for name in measure_columns}
        for row in source.rows:
            key = tuple(row.values.get(item) for item in group_by)
            for name in measure_columns:
                value = row.values.get(name)
                if not isinstance(value, int | float) or isinstance(value, bool):
                    raise RollupDerivationError(f"additive measure must be numeric: {name}")
                if isinstance(value, float) and not value.is_integer():
                    integral[name] = False
                grouped[key][name] += float(value)

        rows: list[DatasetRow] = []
        for key in sorted(grouped, key=semantic_hash):
            values: dict[str, JsonValue] = dict(zip(group_by, key, strict=True))
            values.update(
                {
                    name: int(grouped[key][name]) if integral[name] else grouped[key][name]
                    for name in measure_columns
                }
            )
            rows.append(
                DatasetRow(
                    row_id=stable_row_id(output_dataset_id, group_by, values),
                    values=values,
                )
            )
        dimension_columns = tuple(
            columns_by_name[item].model_copy(update={"nullable": True}) for item in group_by
        )
        output_columns = (
            *dimension_columns,
            *(columns_by_name[name] for name in measure_columns),
        )
        payload = {
            "source_hash": source.content_hash,
            "dataset_id": output_dataset_id,
            "group_by": group_by,
            "measure_columns": measure_columns,
            "rows": [item.model_dump(mode="json") for item in rows],
            "implementation_version": self.IMPLEMENTATION_VERSION,
        }
        content_hash = semantic_hash(payload)
        dataset = TabularDataset(
            object_id=f"ds_{output_dataset_id}_{content_hash[7:15]}",
            created_at=datetime.now(UTC),
            content_hash=content_hash,
            provenance=Provenance(
                producer="analytics.additive_rollup_deriver",
                source_ids=(source.object_id,),
                source_hashes={source.dataset_id: source.content_hash},
                metadata={
                    "implementation_version": self.IMPLEMENTATION_VERSION,
                    "group_by": list(group_by),
                    "measure_columns": list(measure_columns),
                    "required_columns": sorted(required),
                    "task_ids": list(task_ids),
                },
            ),
            dataset_id=output_dataset_id,
            contract_id=f"dc_{output_dataset_id}",
            kind="derived",
            grain=group_by,
            columns=output_columns,
            rows=tuple(rows),
            completeness=source.completeness,
            complete=source.complete,
            truncated=source.truncated,
            source_dataset_ids=(source.dataset_id,),
            derivation_id=f"derive_{output_dataset_id}.v1",
            warnings=source.warnings,
        )
        reconciliation_measure = measure_columns[0]
        source_total = sum(
            value
            for row in source.rows
            if isinstance((value := row.values.get(reconciliation_measure)), int | float)
            and not isinstance(value, bool)
        )
        output_total = sum(
            value
            for row in rows
            if isinstance((value := row.values.get(reconciliation_measure)), int | float)
            and not isinstance(value, bool)
        )
        reconciliation = ReconciliationRecord(
            reconciliation_id=f"reconcile_{output_dataset_id}",
            passed=source_total == output_total,
            expected=source_total,
            actual=output_total,
            message=(
                f"additive Dashboard rollup for {reconciliation_measure} reconciles "
                "to its source Dataset"
            ),
            dataset_ids=(source.dataset_id, output_dataset_id),
        )
        return dataset, reconciliation
