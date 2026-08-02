"""Assemble immutable datasets, QA, and reconciliation into a lineage bundle."""

from datetime import UTC, datetime

from app.contracts.common import Provenance, semantic_hash
from app.contracts.dataset import (
    DataQARecord,
    DatasetBundle,
    ReconciliationRecord,
    TabularDataset,
)
from app.persistence.ids import new_id


class DatasetBundleBuilder:
    def build(
        self,
        datasets: tuple[TabularDataset, ...],
        *,
        data_qa: tuple[DataQARecord, ...] = (),
        reconciliation: tuple[ReconciliationRecord, ...] = (),
    ) -> DatasetBundle:
        if not datasets:
            raise ValueError("dataset bundle cannot be empty")
        dataset_ids = [item.dataset_id for item in datasets]
        if len(dataset_ids) != len(set(dataset_ids)):
            raise ValueError("dataset IDs must be unique within a bundle")
        failed_qa = tuple(item for item in data_qa if not item.passed)
        complete = (
            all(item.complete for item in datasets)
            and not any(item.severity in {"ERROR", "FATAL"} for item in failed_qa)
            and all(item.passed for item in reconciliation)
        )
        warnings = tuple(
            dict.fromkeys(
                [warning for dataset in datasets for warning in dataset.warnings]
                + [item.message for item in failed_qa]
                + [item.message for item in reconciliation if not item.passed]
            )
        )
        payload = {
            "datasets": [item.model_dump(mode="json") for item in datasets],
            "data_qa": [item.model_dump(mode="json") for item in data_qa],
            "reconciliation": [item.model_dump(mode="json") for item in reconciliation],
            "complete": complete,
            "warnings": warnings,
        }
        return DatasetBundle(
            object_id=new_id("db"),
            created_at=datetime.now(UTC),
            content_hash=semantic_hash(payload),
            provenance=Provenance(
                producer="analytics.dataset_bundle_builder",
                source_ids=tuple(item.object_id for item in datasets),
            ),
            datasets=datasets,
            data_qa=data_qa,
            reconciliation=reconciliation,
            complete=complete,
            warnings=warnings,
        )
