"""Config-selected field measures compile and normalize without field-name branches."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.analytics.contract_factory import DatasetContractFactory
from app.analytics.normalizer import ResultNormalizer
from app.analytics.parser import RawResultParser
from app.contracts.common import Provenance, TimeRange, semantic_hash
from app.contracts.execution import RawSearchResult, ShardSummary
from app.contracts.metric import AggregationKind, AggregationParameters
from app.contracts.query import QueryPlan, QueryStep
from app.query.compiler import DslCompiler
from app.semantic.package import CompiledSemanticPackage

ROOT = Path(__file__).resolve().parents[4]
PACKAGE = CompiledSemanticPackage(ROOT / "compiled-semantic" / "mock")


def _plan(*field_measures):
    time_range = TimeRange(
        from_inclusive=datetime(2026, 7, 1, tzinfo=UTC),
        to_exclusive=datetime(2026, 8, 1, tzinfo=UTC),
        timezone="Asia/Hong_Kong",
    )
    step = QueryStep(
        step_id="generic_measure_step",
        purpose_task_ids=("generic_measure_task",),
        dataset_id="sub_message",
        index_patterns=("tbl_os_sub_message_2026_07",),
        time_range=time_range,
        time_field_id="sub_message.event_time",
        filters=(),
        dimensions=("sub_message.channel",),
        measures=(),
        field_measures=field_measures,
        grain=("sub_message.channel",),
        result_contract_id="dc_generic_measure",
        estimated_buckets=10,
    )
    payload = step.model_dump(mode="json")
    return QueryPlan(
        object_id="qp_generic_measure",
        created_at=datetime.now(UTC),
        content_hash=semantic_hash(payload),
        provenance=Provenance(producer="tests.generic_measure"),
        analysis_plan_id="ap_generic_measure",
        steps=(step,),
        total_estimated_buckets=10,
    )


@pytest.mark.parametrize(
    "aggregation,parameters",
    [
        (AggregationKind.VALUE_COUNT, AggregationParameters()),
        (AggregationKind.SUM, AggregationParameters()),
        (AggregationKind.AVG, AggregationParameters()),
        (AggregationKind.MIN, AggregationParameters()),
        (AggregationKind.MAX, AggregationParameters()),
        (AggregationKind.STATS, AggregationParameters()),
        (AggregationKind.EXTENDED_STATS, AggregationParameters(sigma=2)),
        (
            AggregationKind.PERCENTILES,
            AggregationParameters(percents=(50.0, 95.0, 99.0)),
        ),
    ],
)
def test_numeric_measure_aggregation_is_compiled_from_registry_capability(
    aggregation: AggregationKind, parameters: AggregationParameters
) -> None:
    definition = next(
        item for item in PACKAGE.measures() if item.measure_id == "generic_quality_score"
    )
    specification = definition.aggregation_spec(aggregation, parameters)
    compiled = DslCompiler(fields=PACKAGE.fields(), metrics=PACKAGE.metrics()).compile(
        _plan(specification), "generic_measure_step"
    )

    serialized = compiled.model_dump_json()
    assert f'"{aggregation.value}"' in serialized
    assert '"field":"quality_score"' in serialized
    assert compiled.semantics.field_measures == (specification,)


def test_cardinality_parameters_are_allowlisted_and_compiled() -> None:
    definition = next(
        item for item in PACKAGE.measures() if item.measure_id == "unique_message_identifier"
    )
    specification = definition.aggregation_spec()
    compiled = DslCompiler(fields=PACKAGE.fields(), metrics=PACKAGE.metrics()).compile(
        _plan(specification), "generic_measure_step"
    )

    assert '"precision_threshold":3000' in compiled.model_dump_json()
    assert compiled.semantics.field_measures[0].approximate


def test_multi_value_aggregations_become_typed_dataset_columns() -> None:
    definition = next(
        item for item in PACKAGE.measures() if item.measure_id == "generic_quality_score"
    )
    stats = definition.aggregation_spec(AggregationKind.EXTENDED_STATS)
    percentiles = definition.aggregation_spec(
        AggregationKind.PERCENTILES,
        AggregationParameters(percents=(50.0, 95.0)),
    )
    compiled = DslCompiler(fields=PACKAGE.fields(), metrics=PACKAGE.metrics()).compile(
        _plan(stats, percentiles), "generic_measure_step"
    )
    contract = DatasetContractFactory(fields=PACKAGE.fields()).build(compiled)
    channel_agg = compiled.semantics.bucket_path[0].aggregation_name
    raw = RawSearchResult(
        query_id=compiled.object_id,
        took_ms=2,
        timed_out=False,
        shards=ShardSummary(total=1, successful=1, skipped=0, failed=0),
        aggregations={
            channel_agg: {
                "buckets": [
                    {
                        "key": "SYNTHETIC_A",
                        "doc_count": 3,
                        stats.aggregation_name: {
                            "count": 3,
                            "min": 0.5,
                            "max": 0.9,
                            "avg": 0.7,
                            "sum": 2.1,
                            "sum_of_squares": 1.55,
                            "variance": 0.0267,
                            "std_deviation": 0.1633,
                        },
                        percentiles.aggregation_name: {"values": {"50.0": 0.7, "95.0": 0.88}},
                    }
                ]
            }
        },
        raw_size_bytes=512,
    )
    dataset = ResultNormalizer().normalize(RawResultParser().parse(compiled, raw), contract)
    row = dataset.rows[0].values

    assert row["generic_quality_score_v1_extended_stats_avg"] == 0.7
    assert row["generic_quality_score_v1_extended_stats_std_deviation"] == 0.1633
    assert row["generic_quality_score_v1_percentiles_p95"] == 0.88
    typed = {column.name: column for column in dataset.columns}
    assert typed["generic_quality_score_v1_extended_stats_avg"].measure_id == (
        "generic_quality_score.v1"
    )
    assert typed["generic_quality_score_v1_percentiles_p95"].aggregation == "percentiles"
