"""Gateway request/response and execution records."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.contracts.common import JsonValue, Sha256, StrictModel, VersionedModel
from app.contracts.query import QueryStepStatus


class ShardSummary(StrictModel):
    total: int = Field(ge=0)
    successful: int = Field(ge=0)
    skipped: int = Field(ge=0)
    failed: int = Field(ge=0)


class RawSearchResult(StrictModel):
    query_id: str
    took_ms: int = Field(ge=0)
    timed_out: bool
    shards: ShardSummary
    hits_total: int | None = Field(default=None, ge=0)
    aggregations: dict[str, JsonValue]
    hits: tuple[dict[str, JsonValue], ...] = ()
    raw_size_bytes: int = Field(ge=0)
    gateway_metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ExecutionRecord(VersionedModel):
    query_id: str
    query_fingerprint: str
    step_id: str
    status: QueryStepStatus
    started_at: datetime
    completed_at: datetime | None = None
    attempt: int = Field(default=1, ge=1)
    raw_result_hash: Sha256 | None = None
    raw_artifact_id: str | None = None
    source_table_artifact_id: str | None = None
    page_count: int = Field(default=0, ge=0)
    bucket_count: int = Field(default=0, ge=0)
    row_count: int = Field(default=0, ge=0)
    complete: bool = False
    partial: bool = False
    timed_out: bool = False
    shard_failures: int = Field(default=0, ge=0)
    error_code: str | None = None
    retryable: bool = False
    gateway_mode: Literal["mock", "mcp", "direct"]
