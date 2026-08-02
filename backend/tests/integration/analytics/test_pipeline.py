"""Gateway execution flows into reproducible datasets, metrics, QA, and features."""

from pathlib import Path

import pytest

from app.analytics.pipeline import AnalyticsPipeline
from app.contracts.execution import RawSearchResult, ShardSummary
from app.contracts.query import BucketPathItem
from app.gateway.executor import GatewayExecutor
from app.gateway.mock import MockOpenSearchGateway
from app.semantic.package import CompiledSemanticPackage
from tests.unit.gateway.test_mock import compiled_query

PACKAGE_DIR = Path(__file__).parents[4] / "compiled-semantic" / "mock"


def _status_query():
    query = compiled_query()
    bucket_path = (
        BucketPathItem(
            aggregation_name="channel",
            dimension_id="sub_message.channel",
            bucket_kind="terms",
        ),
        BucketPathItem(
            aggregation_name="status",
            dimension_id="sub_message.status",
            bucket_kind="terms",
        ),
    )
    semantics = query.semantics.model_copy(
        update={
            "field_ids": (
                "sub_message.event_time",
                "sub_message.channel",
                "sub_message.status",
            ),
            "metric_ids": ("failure_rate.v1",),
            "grain": ("sub_message.channel", "sub_message.status"),
            "bucket_path": bucket_path,
        }
    )
    return query.model_copy(
        update={
            "object_id": "qry_analytics",
            "result_contract_id": "dc_channel_status_base",
            "semantics": semantics,
        }
    )


def _raw(*, failed_shards: int = 0) -> RawSearchResult:
    successful = 1 - failed_shards
    return RawSearchResult(
        query_id="qry_analytics",
        took_ms=8,
        timed_out=False,
        shards=ShardSummary(
            total=1,
            successful=successful,
            skipped=0,
            failed=failed_shards,
        ),
        aggregations={
            "channel": {
                "buckets": [
                    {
                        "key": "SMS",
                        "doc_count": 100,
                        "status": {
                            "buckets": [
                                {"key": "DELIVERED", "doc_count": 70},
                                {"key": "FAILED", "doc_count": 20},
                                {"key": "PENDING", "doc_count": 5},
                                {"key": "UNKNOWN", "doc_count": 5},
                            ]
                        },
                    },
                    {
                        "key": "EMAIL",
                        "doc_count": 40,
                        "status": {
                            "buckets": [
                                {"key": "SENT", "doc_count": 30},
                                {"key": "REJECTED", "doc_count": 10},
                            ]
                        },
                    },
                ]
            }
        },
        raw_size_bytes=1024,
    )


async def _run_pipeline(raw: RawSearchResult, *, later_page_failed_shards: int = 0):
    query = _status_query()
    gateway = MockOpenSearchGateway()
    gateway.register(query.query_fingerprint, raw)
    execution = await GatewayExecutor(gateway, mode="mock").execute(query)
    assert execution.result is not None
    package = CompiledSemanticPackage(PACKAGE_DIR)
    execution_records = (execution.record,)
    if later_page_failed_shards:
        execution_records = (
            execution.record,
            execution.record.model_copy(
                update={
                    "object_id": "exe_later_page",
                    "shard_failures": later_page_failed_shards,
                }
            ),
        )
    return AnalyticsPipeline(
        metric_definitions=package.metrics(),
        value_dictionaries=package.values(),
    ).process(query, execution.result, execution_records)


@pytest.mark.asyncio
async def test_failure_rate_pipeline_is_complete_and_feature_ready() -> None:
    result = await _run_pipeline(_raw())
    assert not result.fatal
    assert result.bundle.complete
    assert len(result.bundle.datasets) == 3
    base, derived, overall = result.bundle.datasets
    assert len(base.rows) == 6
    assert len(derived.rows) == 2
    sms = next(row for row in derived.rows if row.values["sub_message.channel"] == "SMS")
    metadata = sms.values["metric_metadata"]["failure_rate"]
    assert sms.values["failure_rate.v1"] == 0.2222
    assert metadata["numerator"] == 20
    assert metadata["denominator"] == 90
    assert metadata["excluded"] == {"pending": 5, "unknown": 5}
    assert result.bundle.reconciliation[0].passed
    assert overall.grain == ()
    assert {item.dataset_id for item in result.feature_summaries} == {
        base.dataset_id,
        derived.dataset_id,
        overall.dataset_id,
    }


@pytest.mark.asyncio
async def test_required_shard_failure_is_fatal_and_never_enters_features() -> None:
    result = await _run_pipeline(_raw(failed_shards=1))
    assert result.fatal
    assert not result.bundle.complete
    assert result.feature_summaries == ()
    assert any(
        item.rule_id == "qa_shard_failure" and item.severity == "FATAL" and not item.passed
        for item in result.bundle.data_qa
    )


@pytest.mark.asyncio
async def test_later_composite_page_shard_failure_is_not_lost() -> None:
    result = await _run_pipeline(_raw(), later_page_failed_shards=1)

    assert result.fatal
    assert result.feature_summaries == ()
    assert any(
        item.rule_id == "qa_shard_failure" and not item.passed for item in result.bundle.data_qa
    )
