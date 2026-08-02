"""Composite pages become complete only after the last after_key is consumed."""

from app.analytics.composite import CompositeMergeError, CompositeResultMerger
from app.contracts.execution import RawSearchResult, ShardSummary


def _page(query_id: str, buckets: list[dict], after_key: dict | None) -> RawSearchResult:
    root = {"buckets": buckets}
    if after_key is not None:
        root["after_key"] = after_key
    return RawSearchResult(
        query_id=query_id,
        took_ms=2,
        timed_out=False,
        shards=ShardSummary(total=1, successful=1, skipped=0, failed=0),
        aggregations={"composite_root": root},
        raw_size_bytes=100,
    )


def test_two_composite_pages_merge_with_complete_metadata() -> None:
    merged = CompositeResultMerger().merge(
        (
            _page(
                "qry_pages",
                [{"key": {"channel": "EMAIL"}, "doc_count": 7}],
                {"channel": "EMAIL"},
            ),
            _page(
                "qry_pages",
                [{"key": {"channel": "SMS"}, "doc_count": 10}],
                None,
            ),
        )
    )
    assert len(merged.aggregations["composite_root"]["buckets"]) == 2
    assert merged.gateway_metadata == {"composite_complete": True, "composite_pages": 2}
    assert merged.raw_size_bytes == 200


def test_composite_merge_rejects_duplicate_keys() -> None:
    page = _page(
        "qry_pages",
        [{"key": {"channel": "SMS"}, "doc_count": 10}],
        None,
    )
    try:
        CompositeResultMerger().merge((page, page))
    except CompositeMergeError as error:
        assert "duplicate" in str(error)
    else:
        raise AssertionError("duplicate composite key must be rejected")
