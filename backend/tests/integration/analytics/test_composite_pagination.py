"""Composite aggregation pages are exhausted and merged before analytics starts."""

from typing import Any, cast

import pytest

from app.contracts.execution import RawSearchResult, ShardSummary
from app.contracts.query import BucketPathItem
from app.gateway.bindings import GatewayHealth
from app.gateway.executor import GatewayExecutor
from app.orchestration.phase4_nodes import Phase4Nodes
from app.query.compiler import DslCompiler
from tests.unit.gateway.test_mock import compiled_query


class TwoPageGateway:
    async def execute_search(self, query):
        root = query.query_dsl["aggs"]["composite_root"]
        assert root["composite"]["after"] == {"dim_00_channel": "EMAIL"}
        return _page(
            query.object_id,
            [{"key": {"dim_00_channel": "SMS"}, "doc_count": 7}],
        )

    async def health(self) -> GatewayHealth:
        return GatewayHealth(ready=True, mode="mock")


def _page(query_id: str, buckets: list[dict[str, object]], *, after: bool = False):
    root: dict[str, object] = {"buckets": buckets}
    if after:
        root["after_key"] = {"dim_00_channel": "EMAIL"}
    return RawSearchResult(
        query_id=query_id,
        took_ms=1,
        timed_out=False,
        shards=ShardSummary(total=1, successful=1, skipped=0, failed=0),
        aggregations={"composite_root": root},
        raw_size_bytes=100,
    )


def _query():
    query = compiled_query()
    path = (
        BucketPathItem(
            aggregation_name="dim_00_channel",
            dimension_id="sub_message.channel",
            bucket_kind="composite",
            key_field="composite_root",
        ),
    )
    return query.model_copy(
        update={
            "query_dsl": {
                "size": 0,
                "track_total_hits": False,
                "query": {"bool": {"filter": []}},
                "aggs": {
                    "composite_root": {
                        "composite": {
                            "size": 500,
                            "sources": [{"dim_00_channel": {"terms": {"field": "channel"}}}],
                        }
                    }
                },
            },
            "semantics": query.semantics.model_copy(update={"bucket_path": path}),
        }
    )


def _phase4(*, max_pages: int = 20) -> Phase4Nodes:
    return Phase4Nodes(
        sessions=cast(Any, None),
        executor=GatewayExecutor(TwoPageGateway(), mode="mock", max_attempts=1),
        compiler=DslCompiler(fields=(), metrics=()),
        validator=cast(Any, None),
        analytics=cast(Any, None),
        semantic_package_version="test",
        max_composite_pages=max_pages,
        max_raw_response_bytes=1000,
    )


@pytest.mark.asyncio
async def test_two_composite_pages_are_merged_and_marked_complete() -> None:
    query = _query()
    first = _page(
        query.object_id,
        [{"key": {"dim_00_channel": "EMAIL"}, "doc_count": 3}],
        after=True,
    )

    completed = await _phase4()._complete_composite(query, first)

    assert completed.error_code is None
    assert completed.result is not None
    root = completed.result.aggregations["composite_root"]
    assert root["buckets"] == [
        {"key": {"dim_00_channel": "EMAIL"}, "doc_count": 3},
        {"key": {"dim_00_channel": "SMS"}, "doc_count": 7},
    ]
    assert completed.result.gateway_metadata["composite_complete"] is True
    assert completed.result.gateway_metadata["composite_pages"] == 2
    assert completed.result.gateway_metadata["composite_after_keys"] == [
        {"dim_00_channel": "EMAIL"}
    ]
    assert len(completed.execution_records) == 1


@pytest.mark.asyncio
async def test_composite_page_limit_fails_closed_instead_of_using_partial_data() -> None:
    query = _query()
    first = _page(
        query.object_id,
        [{"key": {"dim_00_channel": "EMAIL"}, "doc_count": 3}],
        after=True,
    )

    completed = await _phase4(max_pages=1)._complete_composite(query, first)

    assert completed.result is None
    assert completed.error_code == "GW_COMPOSITE_PAGE_LIMIT"
