"""Mock Gateway is fingerprint-addressed and records retries/call counts."""

from datetime import UTC, datetime

import pytest

from app.contracts.common import Provenance, TimeRange, semantic_hash
from app.contracts.execution import RawSearchResult, ShardSummary
from app.contracts.query import CompiledQuery, QuerySemantics
from app.gateway.errors import GatewayProtocolError, GatewayTimeoutError
from app.gateway.executor import GatewayExecutor
from app.gateway.mock import MockOpenSearchGateway


def compiled_query() -> CompiledQuery:
    time_range = TimeRange(
        from_inclusive=datetime(2026, 7, 1, tzinfo=UTC),
        to_exclusive=datetime(2026, 8, 1, tzinfo=UTC),
        timezone="Asia/Hong_Kong",
    )
    semantics = QuerySemantics(
        dataset_id="sub_message",
        time_range=time_range,
        time_field_id="sub_message.event_time",
        field_ids=("sub_message.event_time",),
        metric_ids=("message_record_count.v1",),
        filter_fingerprint=semantic_hash([]),
        grain=(),
        bucket_path=(),
    )
    return CompiledQuery(
        object_id="qry_mock",
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        content_hash=semantic_hash({"query": "mock"}),
        provenance=Provenance(producer="tests.gateway"),
        query_plan_id="qp_mock",
        step_id="q1_base",
        indices=("tbl_os_sub_message_2026_07",),
        query_dsl={"size": 0, "query": {"bool": {"filter": []}}, "aggs": {}},
        semantics=semantics,
        query_fingerprint="sha256:" + "1" * 64,
        timeout_ms=30000,
        result_contract_id="dc_q1_base",
    )


def raw_result() -> RawSearchResult:
    return RawSearchResult(
        query_id="qry_mock",
        took_ms=5,
        timed_out=False,
        shards=ShardSummary(total=1, successful=1, skipped=0, failed=0),
        aggregations={},
        raw_size_bytes=64,
    )


@pytest.mark.asyncio
async def test_mock_fault_then_success_records_exact_call_count() -> None:
    query = compiled_query()
    gateway = MockOpenSearchGateway()
    gateway.register(query.query_fingerprint, GatewayTimeoutError("timeout"), raw_result())
    with pytest.raises(GatewayTimeoutError):
        await gateway.execute_search(query)
    assert await gateway.execute_search(query) == raw_result()
    assert gateway.calls[query.query_fingerprint] == 2
    assert gateway.total_calls == 2
    assert (await gateway.health()).ready


@pytest.mark.asyncio
async def test_executor_retries_only_retryable_gateway_failures() -> None:
    query = compiled_query()
    retry_gateway = MockOpenSearchGateway()
    retry_gateway.register(query.query_fingerprint, GatewayTimeoutError("timeout"), raw_result())
    successful = await GatewayExecutor(retry_gateway, mode="mock", max_attempts=2).execute(query)
    assert successful.result == raw_result()
    assert successful.record.status.value == "SUCCEEDED"
    assert successful.record.attempt == 2

    terminal_gateway = MockOpenSearchGateway()
    terminal_gateway.register(query.query_fingerprint, GatewayProtocolError("invalid"))
    failed = await GatewayExecutor(terminal_gateway, mode="mock", max_attempts=3).execute(query)
    assert failed.result is None
    assert failed.record.error_code == "GW_PROTOCOL"
    assert failed.record.attempt == 1
    assert terminal_gateway.total_calls == 1
