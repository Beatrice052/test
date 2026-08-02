"""Governed derivation, Metric Engine, statistics, QA, and features stay deterministic."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.analytics.derivation import DerivationResult, StatusMetricDeriver
from app.analytics.features import FeatureSummaryBlocked, FeatureSummaryBuilder
from app.analytics.identity import stable_row_id
from app.analytics.qa import DataQAEngine
from app.analytics.statistics import StatisticEngine
from app.contracts.common import Provenance, semantic_hash
from app.contracts.dataset import (
    DatasetColumn,
    DatasetCompleteness,
    DatasetRow,
    TabularDataset,
)
from app.contracts.metric import MetricValue
from app.semantic.package import CompiledSemanticPackage

PACKAGE_DIR = Path(__file__).parents[4] / "compiled-semantic" / "mock"


def _base_dataset() -> TabularDataset:
    raw_rows = (
        ("SMS", "DELIVERED", 70),
        ("SMS", "FAILED", 20),
        ("SMS", "PENDING", 5),
        ("SMS", "UNKNOWN", 5),
        ("EMAIL", "PENDING", 3),
        ("EMAIL", "UNKNOWN", 2),
        ("SMALL", "SENT", 10),
        ("SMALL", "FAILED", 2),
    )
    rows = tuple(
        DatasetRow(
            row_id=stable_row_id(
                "channel_status_base",
                ("sub_message.channel", "sub_message.status"),
                {"sub_message.channel": channel, "sub_message.status": status},
            ),
            values={
                "sub_message.channel": channel,
                "sub_message.status": status,
                "record_count": count,
            },
        )
        for channel, status, count in raw_rows
    )
    payload = [item.model_dump(mode="json") for item in rows]
    return TabularDataset(
        object_id="ds_channel_status_base_deadbeef",
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        content_hash=semantic_hash(payload),
        provenance=Provenance(producer="tests.analytics"),
        dataset_id="channel_status_base",
        contract_id="dc_channel_status_base",
        kind="base",
        grain=("sub_message.channel", "sub_message.status"),
        columns=(
            DatasetColumn(
                name="sub_message.channel",
                data_type="string",
                nullable=False,
                semantic_role="dimension",
                field_id="sub_message.channel",
            ),
            DatasetColumn(
                name="sub_message.status",
                data_type="string",
                nullable=True,
                semantic_role="dimension",
                field_id="sub_message.status",
            ),
            DatasetColumn(
                name="record_count",
                data_type="integer",
                nullable=False,
                semantic_role="measure",
                unit="count",
            ),
        ),
        rows=rows,
        completeness=DatasetCompleteness.COMPLETE,
        complete=True,
        truncated=False,
    )


def _derive() -> DerivationResult:
    package = CompiledSemanticPackage(PACKAGE_DIR)
    return StatusMetricDeriver().derive(
        _base_dataset(),
        output_dataset_id="channel_metrics",
        derivation_id="derive_channel_metrics.v1",
        group_by=("sub_message.channel",),
        status_field_id="sub_message.status",
        value_dictionary=package.values()[0],
        metric_definitions=package.metrics(),
    )


def test_failure_rate_uses_registry_numerator_denominator_and_exclusions() -> None:
    result = _derive()
    by_channel = {
        row.values["sub_message.channel"]: (row, result.metric_values_by_row[row.row_id])
        for row in result.dataset.rows
    }
    sms_row, sms_metrics = by_channel["SMS"]
    failure = next(item for item in sms_metrics if item.metric_id == "failure_rate")
    count = next(item for item in sms_metrics if item.metric_id == "message_record_count")
    assert failure.value == 0.2222
    assert failure.numerator == 20
    assert failure.denominator == 90
    assert failure.excluded == {"pending": 5, "unknown": 5}
    assert failure.quality == "VALID"
    assert count.value == 100
    assert set(failure.evidence_row_ids).issubset({item.row_id for item in _base_dataset().rows})
    assert sms_row.values["failure_rate.v1"] == 0.2222

    email_metrics = by_channel["EMAIL"][1]
    email_failure = next(item for item in email_metrics if item.metric_id == "failure_rate")
    assert email_failure.denominator == 0
    assert email_failure.value is None
    assert email_failure.quality == "INVALID"

    small_metrics = by_channel["SMALL"][1]
    small_failure = next(item for item in small_metrics if item.metric_id == "failure_rate")
    assert small_failure.denominator == 12
    assert small_failure.quality == "INSUFFICIENT_SAMPLE"


def test_derivation_content_hash_and_reconciliation_are_reproducible() -> None:
    first = _derive()
    second = _derive()
    assert first.dataset.content_hash == second.dataset.content_hash
    assert first.dataset.object_id == second.dataset.object_id
    assert first.dataset.provenance.metadata["implementation_version"] == "1.0"
    assert first.reconciliation[0].passed
    assert first.reconciliation[0].expected == 117
    assert first.reconciliation[0].actual == 117


def test_qa_warns_for_unknown_and_small_sample_but_allows_features() -> None:
    derived = _derive()
    qa = DataQAEngine().evaluate(
        derived.dataset,
        metric_values_by_row=derived.metric_values_by_row,
        reconciliation=derived.reconciliation,
        rederived_content_hash=_derive().dataset.content_hash,
    )
    failed_codes = {item.rule_id for item in qa if not item.passed}
    assert failed_codes == {"qa_unknown_status", "qa_small_sample"}
    summary = FeatureSummaryBuilder().build(
        derived.dataset,
        statistical_results=(
            StatisticEngine().compute(
                "rank", derived.dataset, {"column": "message_record_count.v1", "n": 2}
            ),
        ),
        qa_records=qa,
    )
    assert summary.row_count == 3
    assert summary.statistical_results[0].applicability == "APPLICABLE"
    assert summary.qa_summary == {"WARNING": 2}
    assert len(summary.sample_rows) == 3


def test_fatal_metric_violation_blocks_feature_summary() -> None:
    derived = _derive()
    row_id = derived.dataset.rows[0].row_id
    invalid = MetricValue(
        metric_id="failure_rate",
        metric_version="v1",
        value=1.2,
        unit="ratio",
        numerator=12,
        denominator=10,
        quality="INVALID",
        evidence_row_ids=(row_id,),
    )
    qa = DataQAEngine().evaluate(
        derived.dataset,
        metric_values_by_row={row_id: (invalid,)},
        rederived_content_hash=derived.dataset.content_hash,
    )
    assert {item.rule_id for item in qa if item.severity == "FATAL" and not item.passed} == {
        "qa_ratio_bounds",
        "qa_numerator_le_denominator",
    }
    with pytest.raises(FeatureSummaryBlocked):
        FeatureSummaryBuilder().build(derived.dataset, qa_records=qa)


def test_governed_statistical_catalog_executes_deterministically() -> None:
    rows = tuple(
        DatasetRow(
            row_id=stable_row_id(
                "statistical_catalog",
                ("day",),
                {"day": f"2026-07-{index:02d}T00:00:00+00:00"},
            ),
            values={
                "day": f"2026-07-{index:02d}T00:00:00+00:00",
                "record_count": value,
            },
        )
        for index, value in enumerate(
            [10, 11, 9, 12, 10, 13, 11, 12, 10, 14, 12, 13, 11, 15, 50],
            start=1,
        )
    )
    dataset = TabularDataset(
        object_id="ds_statistical_catalog",
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        content_hash=semantic_hash([item.model_dump(mode="json") for item in rows]),
        provenance=Provenance(producer="tests.statistics"),
        dataset_id="statistical_catalog",
        contract_id="dc_statistical_catalog",
        kind="derived",
        grain=("day",),
        columns=(
            DatasetColumn(
                name="day",
                data_type="datetime",
                nullable=False,
                semantic_role="dimension",
                semantic_type="time_dimension",
            ),
            DatasetColumn(
                name="record_count",
                data_type="integer",
                nullable=False,
                semantic_role="measure",
                unit="count",
            ),
        ),
        rows=rows,
        completeness=DatasetCompleteness.COMPLETE,
        complete=True,
        truncated=False,
    )
    engine = StatisticEngine()
    params = {"column": "record_count", "time_column": "day", "window": 7}
    method_ids = (
        "rank",
        "contribution",
        "mean_median",
        "percentiles",
        "std_cv",
        "moving_average",
        "mad_robust_zscore",
        "hhi",
        "pareto",
        "peak_to_average",
        "trend_slope",
        "period_change",
    )

    results = {item: engine.compute(item, dataset, params) for item in method_ids}

    assert set(results) == set(method_ids)
    assert all(item.applicability == "APPLICABLE" for item in results.values())
    assert results["percentiles"].values["percentiles"] == {
        "p50": 12.0,
        "p95": pytest.approx(25.5),
        "p99": pytest.approx(45.1),
    }
    assert len(results["moving_average"].values["points"]) == 9
    assert results["pareto"].values["points"][0]["value"] == 50.0
    assert results["period_change"].values["absolute_change"] == 40.0


def test_statistic_methods_return_not_applicable_instead_of_system_failure() -> None:
    derived = _derive()
    engine = StatisticEngine()
    contribution = engine.compute(
        "contribution", derived.dataset, {"column": "message_record_count.v1"}
    )
    assert contribution.applicability == "APPLICABLE"
    assert contribution.values["total"] == 117.0
    mad = engine.compute(
        "mad_robust_zscore", derived.dataset, {"column": "message_record_count.v1"}
    )
    assert mad.applicability == "NOT_APPLICABLE"
    unknown = engine.compute("invented_method", derived.dataset, {})
    assert unknown.applicability == "NOT_APPLICABLE"
