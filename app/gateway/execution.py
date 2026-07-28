from __future__ import annotations

from typing import Any, Protocol
from uuid import uuid4

from app.gateway.models import (
    ExecutionBundle,
    ExecutionRecord,
    ExecutionStep,
    GatewayCapabilities,
    RawQueryResult,
)
from app.query.models import CompiledQuery


class OpenSearchTransport(Protocol):
    def count(self, index: str, query: dict[str, Any]) -> dict[str, Any]: ...

    def search(self, index: str, body: dict[str, Any]) -> dict[str, Any]: ...

    def msearch(self, requests: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


def plan_execution(
    queries: list[CompiledQuery], capabilities: GatewayCapabilities
) -> list[ExecutionStep]:
    if not queries:
        return []
    if len(queries) == 1:
        query = queries[0]
        if query.query_type in {"count", "filtered_count"}:
            return [
                ExecutionStep(
                    gateway_method="count",
                    mcp_tool="CountTool",
                    reason_code="PURE_COUNT",
                    requests=[_request(query)],
                )
            ]
        return [
            ExecutionStep(
                gateway_method="search",
                mcp_tool="SearchIndexTool",
                reason_code="SEARCH_OR_AGGREGATION",
                requests=[_request(query)],
            )
        ]
    if capabilities.msearch:
        return [
            ExecutionStep(
                gateway_method="msearch",
                mcp_tool="MsearchTool",
                reason_code="MULTIPLE_INDEPENDENT_QUERIES",
                requests=[_request(query) for query in queries],
            )
        ]
    return [
        ExecutionStep(
            gateway_method=(
                "count" if query.query_type in {"count", "filtered_count"} else "search"
            ),
            mcp_tool=(
                "CountTool"
                if query.query_type in {"count", "filtered_count"}
                else "SearchIndexTool"
            ),
            reason_code="SEQUENTIAL_QUERY",
            requests=[_request(query)],
        )
        for query in queries
    ]


def execute_queries(
    transport: OpenSearchTransport,
    queries: list[CompiledQuery],
    capabilities: GatewayCapabilities,
) -> ExecutionBundle:
    query_map = {query.query_id: query for query in queries}
    records: list[ExecutionRecord] = []
    results: list[RawQueryResult] = []
    for step in plan_execution(queries, capabilities):
        if step.gateway_method == "msearch":
            payloads = transport.msearch(step.requests)
        else:
            request = step.requests[0]
            payloads = [
                transport.count(request["index"], request["body"])
                if step.gateway_method == "count"
                else transport.search(request["index"], request["body"])
            ]
        query_ids = [str(request["query_id"]) for request in step.requests]
        records.append(
            ExecutionRecord(
                execution_id=f"execution-{uuid4()}",
                query_ids=query_ids,
                gateway_method=step.gateway_method,
                mcp_tool=step.mcp_tool,
                reason_code=step.reason_code,
                arguments_preview={
                    "indices": [request["index"] for request in step.requests],
                    "request_count": len(step.requests),
                },
                status="SUCCEEDED",
            )
        )
        for request, payload in zip(step.requests, payloads, strict=True):
            query = query_map[str(request["query_id"])]
            results.append(
                RawQueryResult(
                    query_id=query.query_id,
                    logical_query_id=query.logical_query_id,
                    index=query.index,
                    query_type=query.query_type,
                    payload=payload,
                )
            )
    return ExecutionBundle(records=records, results=results)


def _request(query: CompiledQuery) -> dict[str, Any]:
    return {
        "query_id": query.query_id,
        "index": query.index,
        "body": query.body,
    }
