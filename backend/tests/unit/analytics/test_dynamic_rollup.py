"""Dynamic grains and rollups are field-name agnostic."""

from datetime import UTC, datetime

from app.analytics.identity import stable_row_id
from app.analytics.pipeline import AnalyticsPipeline
from app.analytics.rollup import AdditiveRollupDeriver
from app.contracts.common import Provenance, semantic_hash
from app.contracts.dataset import (
    DatasetColumn,
    DatasetCompleteness,
    DatasetRow,
    TabularDataset,
)


def _source() -> TabularDataset:
    columns = (
        DatasetColumn(
            name="telemetry.occurred_at",
            data_type="datetime",
            nullable=False,
            semantic_role="dimension",
            semantic_type="time_dimension",
        ),
        DatasetColumn(
            name="telemetry.region_key",
            data_type="string",
            nullable=False,
            semantic_role="dimension",
            semantic_type="categorical_dimension",
        ),
        DatasetColumn(
            name="telemetry.outcome_key",
            data_type="string",
            nullable=False,
            semantic_role="dimension",
            semantic_type="categorical_dimension",
        ),
        DatasetColumn(
            name="record_count",
            data_type="integer",
            nullable=False,
            semantic_role="measure",
            unit="count",
        ),
    )
    raw = (
        ("2026-01-01T00:00:00Z", "north", "ok", 4),
        ("2026-01-01T00:00:00Z", "north", "failed", 2),
        ("2026-02-01T00:00:00Z", "north", "ok", 5),
        ("2026-02-01T00:00:00Z", "south", "ok", 7),
    )
    rows = tuple(
        DatasetRow(
            row_id=stable_row_id(
                "generic_source",
                ("telemetry.occurred_at", "telemetry.region_key", "telemetry.outcome_key"),
                {
                    "telemetry.occurred_at": period,
                    "telemetry.region_key": region,
                    "telemetry.outcome_key": outcome,
                },
            ),
            values={
                "telemetry.occurred_at": period,
                "telemetry.region_key": region,
                "telemetry.outcome_key": outcome,
                "record_count": count,
            },
        )
        for period, region, outcome, count in raw
    )
    return TabularDataset(
        object_id="ds_generic_source",
        created_at=datetime(2026, 8, 2, tzinfo=UTC),
        content_hash=semantic_hash([item.model_dump(mode="json") for item in rows]),
        provenance=Provenance(producer="tests.dynamic_rollup"),
        dataset_id="generic_source",
        contract_id="dc_generic_source",
        kind="base",
        grain=(
            "telemetry.occurred_at",
            "telemetry.region_key",
            "telemetry.outcome_key",
        ),
        columns=columns,
        rows=rows,
        completeness=DatasetCompleteness.COMPLETE,
        complete=True,
        truncated=False,
    )


def test_metric_view_grains_are_derived_from_semantic_roles_not_field_names() -> None:
    source = _source()
    primary = (
        "telemetry.occurred_at",
        "telemetry.region_key",
        "telemetry.cause_key",
    )
    columns = (
        *source.columns[:2],
        DatasetColumn(
            name="telemetry.cause_key",
            data_type="string",
            nullable=True,
            semantic_role="dimension",
            semantic_type="categorical_dimension",
        ),
    )
    views = AnalyticsPipeline._metric_view_grains(
        type(
            "Query",
            (),
            {"semantics": type("Semantics", (), {"time_field_id": "telemetry.occurred_at"})()},
        )(),
        columns,
        primary,
    )
    grains = {grain for _, grain in views}

    assert () in grains
    assert ("telemetry.region_key",) in grains
    assert ("telemetry.cause_key",) in grains
    assert ("telemetry.occurred_at", "telemetry.region_key") in grains
    assert ("telemetry.occurred_at", "telemetry.cause_key") in grains


def test_additive_rollup_produces_one_row_per_requested_generic_category() -> None:
    source = _source()
    rolled, reconciliation = AdditiveRollupDeriver().derive(
        source,
        output_dataset_id="region_rollup",
        group_by=("telemetry.region_key",),
    )
    values = {row.values["telemetry.region_key"]: row.values["record_count"] for row in rolled.rows}

    assert rolled.grain == ("telemetry.region_key",)
    assert values == {"north": 11, "south": 7}
    assert len(values) == len(rolled.rows)
    assert reconciliation.passed
    assert reconciliation.expected == reconciliation.actual == 18
