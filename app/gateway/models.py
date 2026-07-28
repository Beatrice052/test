from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GatewayModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GatewayCapabilities(GatewayModel):
    list_index: bool = True
    index_mapping: bool = True
    count: bool = True
    search: bool = True
    msearch: bool = True
    generic_api: bool = False
    ppl: bool = False
    read_only: bool = True


class GatewayFault(StrEnum):
    NONE = "NONE"
    QUERY_TIMEOUT = "QUERY_TIMEOUT"
    NO_DATA = "NO_DATA"
    SHARD_FAILURE = "SHARD_FAILURE"
    BUCKET_TRUNCATED = "BUCKET_TRUNCATED"
    METRIC_QA_FAILED = "METRIC_QA_FAILED"


class ExecutionStep(GatewayModel):
    gateway_method: Literal["count", "search", "msearch"]
    mcp_tool: Literal["CountTool", "SearchIndexTool", "MsearchTool"]
    reason_code: str
    requests: list[dict[str, Any]]


class ExecutionRecord(GatewayModel):
    execution_id: str
    query_ids: list[str]
    gateway_method: str
    mcp_tool: str
    reason_code: str
    arguments_preview: dict[str, Any]
    status: Literal["SUCCEEDED", "FAILED"]
    retry_count: int = 0


class RawQueryResult(GatewayModel):
    query_id: str
    logical_query_id: str
    index: str
    query_type: str
    payload: dict[str, Any]


class ExecutionBundle(GatewayModel):
    records: list[ExecutionRecord] = Field(default_factory=list)
    results: list[RawQueryResult] = Field(default_factory=list)
