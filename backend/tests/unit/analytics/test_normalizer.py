"""Result normalization preserves every governed bucket dimension and completeness."""

from app.analytics.contract_factory import DatasetContractFactory
from app.analytics.normalizer import DatasetContractViolation, ResultNormalizer
from app.analytics.parser import RawResultParser
from app.contracts.dataset import DatasetCompleteness
from app.contracts.execution import RawSearchResult, ShardSummary
from app.contracts.query import BucketPathItem
from tests.unit.gateway.test_mock import compiled_query


def _query(*bucket_path: BucketPathItem):
    query = compiled_query()
    semantics = query.semantics.model_copy(
        update={
            "field_ids": tuple(item.dimension_id for item in bucket_path),
            "bucket_path": bucket_path,
            "grain": tuple(item.dimension_id for item in bucket_path),
        }
    )
    return query.model_copy(
        update={
            "object_id": "qry_normalize",
            "result_contract_id": "dc_normalize",
            "semantics": semantics,
        }
    )


def _raw(aggregations: dict, **metadata: object) -> RawSearchResult:
    return RawSearchResult(
        query_id="qry_normalize",
        took_ms=4,
        timed_out=False,
        shards=ShardSummary(total=2, successful=2, skipped=0, failed=0),
        aggregations=aggregations,
        raw_size_bytes=512,
        gateway_metadata=metadata,
    )


def _normalize(query, raw):
    parsed = RawResultParser().parse(query, raw)
    contract = DatasetContractFactory().build(query, dataset_id="month_channel_status_base")
    return ResultNormalizer().normalize(parsed, contract)


def test_recursive_month_channel_status_never_drops_inner_dimensions() -> None:
    query = _query(
        BucketPathItem(
            aggregation_name="month",
            dimension_id="sub_message.event_time",
            bucket_kind="date_histogram",
        ),
        BucketPathItem(
            aggregation_name="channel",
            dimension_id="sub_message.channel",
            bucket_kind="terms",
        ),
        BucketPathItem(
            aggregation_name="status",
            dimension_id="sub_message.status",
            bucket_kind="filters",
        ),
    )
    raw = _raw(
        {
            "month": {
                "buckets": [
                    {
                        "key": 1782835200000,
                        "key_as_string": "2026-07-01T00:00:00+08:00",
                        "doc_count": 30,
                        "channel": {
                            "buckets": [
                                {
                                    "key": "SMS",
                                    "doc_count": 20,
                                    "status": {
                                        "buckets": {
                                            "success": {"doc_count": 17},
                                            "failure": {"doc_count": 3},
                                        }
                                    },
                                },
                                {
                                    "key": "EMAIL",
                                    "doc_count": 10,
                                    "status": {"buckets": {"success": {"doc_count": 10}}},
                                },
                            ]
                        },
                    }
                ]
            }
        }
    )
    dataset = _normalize(query, raw)
    assert dataset.completeness == DatasetCompleteness.COMPLETE
    assert len(dataset.rows) == 3
    assert dataset.rows[0].values == {
        "sub_message.event_time": "2026-07-01T00:00:00+08:00",
        "sub_message.channel": "SMS",
        "sub_message.status": "success",
        "record_count": 17,
    }
    assert all(len(row.row_id) == 20 for row in dataset.rows)


def test_row_id_is_stable_when_measure_changes() -> None:
    query = _query(
        BucketPathItem(
            aggregation_name="channel",
            dimension_id="sub_message.channel",
            bucket_kind="terms",
        )
    )
    first = _normalize(
        query,
        _raw({"channel": {"buckets": [{"key": "SMS", "doc_count": 10}]}}),
    )
    second = _normalize(
        query,
        _raw({"channel": {"buckets": [{"key": "SMS", "doc_count": 11}]}}),
    )
    assert first.rows[0].row_id == second.rows[0].row_id
    assert first.content_hash != second.content_hash


def test_composite_and_nested_wrapper_are_contract_driven() -> None:
    query = _query(
        BucketPathItem(
            aggregation_name="dim_00_channel",
            dimension_id="sub_message.channel",
            bucket_kind="composite",
            key_field="composite_root",
        ),
        BucketPathItem(
            aggregation_name="provider",
            dimension_id="sub_message.metadata.provider",
            bucket_kind="nested",
        ),
    )
    dataset = _normalize(
        query,
        _raw(
            {
                "composite_root": {
                    "after_key": {"dim_00_channel": "SMS"},
                    "buckets": [
                        {
                            "key": {"dim_00_channel": "SMS"},
                            "doc_count": 4,
                            "nested_wrapper": {
                                "doc_count": 4,
                                "provider": {"buckets": [{"key": "acme", "doc_count": 4}]},
                            },
                        }
                    ],
                }
            }
        ),
    )
    assert dataset.completeness == DatasetCompleteness.PARTIAL
    assert dataset.rows[0].values["sub_message.channel"] == "SMS"
    assert dataset.rows[0].values["sub_message.metadata.provider"] == "acme"


def test_terms_completeness_records_truncation_and_others() -> None:
    query = _query(
        BucketPathItem(
            aggregation_name="channel",
            dimension_id="sub_message.channel",
            bucket_kind="terms",
        )
    )
    truncated = _normalize(
        query,
        _raw(
            {
                "channel": {
                    "doc_count_error_upper_bound": 2,
                    "sum_other_doc_count": 9,
                    "buckets": [{"key": "SMS", "doc_count": 10}],
                }
            }
        ),
    )
    assert truncated.completeness == DatasetCompleteness.TRUNCATED
    assert truncated.truncated

    with_others = _normalize(
        query,
        _raw(
            {
                "channel": {
                    "sum_other_doc_count": 9,
                    "buckets": [
                        {"key": "SMS", "doc_count": 10},
                        {"key": "Others", "doc_count": 9},
                    ],
                }
            }
        ),
    )
    assert with_others.completeness == DatasetCompleteness.TOP_N_WITH_OTHERS
    assert with_others.complete


def test_missing_required_inner_aggregation_is_contract_violation() -> None:
    query = _query(
        BucketPathItem(
            aggregation_name="month",
            dimension_id="sub_message.event_time",
            bucket_kind="date_histogram",
        ),
        BucketPathItem(
            aggregation_name="channel",
            dimension_id="sub_message.channel",
            bucket_kind="terms",
        ),
    )
    try:
        _normalize(
            query,
            _raw(
                {
                    "month": {
                        "buckets": [
                            {
                                "key_as_string": "2026-07-01T00:00:00+08:00",
                                "doc_count": 5,
                            }
                        ]
                    }
                }
            ),
        )
    except DatasetContractViolation as error:
        assert "channel" in str(error)
    else:
        raise AssertionError("missing channel aggregation must be rejected")


def test_leaf_metric_object_and_missing_bucket_are_preserved_without_formula_evaluation() -> None:
    query = _query(
        BucketPathItem(
            aggregation_name="channel",
            dimension_id="sub_message.channel",
            bucket_kind="terms",
        )
    )
    dataset = _normalize(
        query,
        _raw(
            {
                "channel": {
                    "buckets": [
                        {
                            "key": None,
                            "doc_count": 4,
                            "latency_p95": {"value": 125.5},
                        }
                    ]
                }
            }
        ),
    )
    assert dataset.rows[0].values["sub_message.channel"] is None
    assert dataset.rows[0].values["raw_metrics"] == {"latency_p95": 125.5}
