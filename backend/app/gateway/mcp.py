"""Official-MCP-facing Gateway adapter with cached, validated tool bindings."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from typing import Protocol, cast

from app.contracts.common import JsonValue
from app.contracts.execution import RawSearchResult, ShardSummary
from app.contracts.query import CompiledQuery
from app.contracts.semantic import MappingSnapshot
from app.gateway.bindings import (
    GatewayBindings,
    GatewayHealth,
    MappingRequest,
    McpCapabilityReport,
    ToolDescriptor,
)
from app.gateway.capability_probe import McpCapabilityProbe
from app.gateway.errors import GatewayCapabilityError, GatewayProtocolError
from app.semantic.mapping import flatten_mapping_snapshot


class McpTransport(Protocol):
    async def list_tools(self) -> tuple[ToolDescriptor, ...]: ...

    async def call_tool(self, name: str, arguments: dict[str, object]) -> object: ...


class McpOpenSearchGateway:
    def __init__(
        self,
        *,
        transport: McpTransport,
        bindings: GatewayBindings,
        max_raw_response_bytes: int = 10_000_000,
    ) -> None:
        self.transport = transport
        self.bindings = bindings
        self.max_raw_response_bytes = max_raw_response_bytes
        self.capabilities: McpCapabilityReport | None = None

    async def probe(self) -> McpCapabilityReport:
        report = McpCapabilityProbe().probe(self.bindings, await self.transport.list_tools())
        self.capabilities = report
        return report

    async def get_mapping(self, request: MappingRequest) -> MappingSnapshot:
        tool = self._tool("get_mapping")
        response = await self.transport.call_tool(tool, {"index": ",".join(request.indices)})
        payload, _ = self._decode(response)
        try:
            return MappingSnapshot.model_validate(payload, strict=False)
        except ValueError as error:
            if isinstance(payload, Mapping):
                try:
                    return flatten_mapping_snapshot(payload, dataset_id=request.dataset_id)
                except ValueError as mapping_error:
                    raise GatewayProtocolError(
                        "MCP mapping response cannot be normalized"
                    ) from mapping_error
            raise GatewayProtocolError("MCP mapping response is not an object") from error

    async def execute_search(self, query: CompiledQuery) -> RawSearchResult:
        tool = self._tool("execute_search")
        if self.capabilities is None:
            raise GatewayCapabilityError("MCP capability probe has not run")
        query_dsl: object = query.query_dsl
        if self.capabilities.query_dsl_mode == "string":
            query_dsl = json.dumps(query.query_dsl, ensure_ascii=False, sort_keys=True)
        response = await self.transport.call_tool(
            tool,
            {
                "index": ",".join(query.indices),
                "query_dsl": query_dsl,
                "format": "json",
            },
        )
        payload, raw_size = self._decode(response)
        if raw_size > self.max_raw_response_bytes:
            raise GatewayProtocolError("MCP response exceeds raw byte budget")
        if isinstance(payload, list):
            return RawSearchResult(
                query_id=query.object_id,
                took_ms=0,
                timed_out=False,
                shards=ShardSummary(total=0, successful=0, skipped=0, failed=0),
                hits=tuple(cast(dict[str, JsonValue], row) for row in payload),
                aggregations={},
                raw_size_bytes=raw_size,
                gateway_metadata={"transport": "mcp", "tool": tool, "format": "csv"},
            )
        if not isinstance(payload, dict):
            raise GatewayProtocolError("MCP search response is not an object")
        shards = payload.get("_shards", payload.get("shards", {}))
        if not isinstance(shards, dict):
            raise GatewayProtocolError("MCP search response has invalid shard metadata")
        hits_payload = payload.get("hits", {})
        hits: tuple[dict[str, JsonValue], ...] = ()
        hits_total: int | None = None
        if isinstance(hits_payload, dict):
            raw_hits = hits_payload.get("hits", ())
            if isinstance(raw_hits, list):
                hits = tuple(cast(dict[str, JsonValue], item) for item in raw_hits)
            total = hits_payload.get("total")
            if isinstance(total, int):
                hits_total = total
            elif isinstance(total, dict) and isinstance(total.get("value"), int):
                hits_total = total["value"]
        aggregations = payload.get("aggregations", {})
        if not isinstance(aggregations, dict):
            raise GatewayProtocolError("MCP aggregations must be an object")
        return RawSearchResult(
            query_id=query.object_id,
            took_ms=self._nonnegative_int(payload.get("took", payload.get("took_ms", 0)), "took"),
            timed_out=bool(payload.get("timed_out", False)),
            shards=ShardSummary(
                total=self._nonnegative_int(shards.get("total", 0), "shards.total"),
                successful=self._nonnegative_int(shards.get("successful", 0), "shards.successful"),
                skipped=self._nonnegative_int(shards.get("skipped", 0), "shards.skipped"),
                failed=self._nonnegative_int(shards.get("failed", 0), "shards.failed"),
            ),
            hits_total=hits_total,
            aggregations=cast(dict[str, JsonValue], aggregations),
            hits=hits,
            raw_size_bytes=raw_size,
            gateway_metadata={"transport": "mcp", "tool": tool},
        )

    async def health(self) -> GatewayHealth:
        if self.capabilities is None:
            report = await self.probe()
        else:
            report = self.capabilities
        return GatewayHealth(
            ready=report.ready,
            mode="mcp",
            details={
                "missing_capabilities": list(report.missing_capabilities),
                "query_dsl_mode": report.query_dsl_mode,
            },
        )

    def _tool(self, capability: str) -> str:
        report = self.capabilities
        if report is None or not report.ready:
            raise GatewayCapabilityError("MCP Gateway is not ready")
        try:
            return report.resolved_bindings[capability]
        except KeyError as error:
            raise GatewayCapabilityError(f"MCP capability is unavailable: {capability}") from error

    @classmethod
    def _decode(cls, response: object) -> tuple[object, int]:
        value = cls._unwrap_content(response)
        if isinstance(value, str):
            raw_size = len(value.encode("utf-8"))
            stripped = value.strip()
            for _ in range(2):
                try:
                    decoded = json.loads(stripped)
                except json.JSONDecodeError:
                    break
                if isinstance(decoded, str):
                    stripped = decoded
                    continue
                return decoded, raw_size
            reader = csv.DictReader(io.StringIO(value))
            rows = [dict(row) for row in reader]
            if reader.fieldnames and rows:
                return rows, raw_size
            raise GatewayProtocolError("MCP text response is neither JSON nor CSV")
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
        return value, len(serialized.encode("utf-8"))

    @staticmethod
    def _unwrap_content(response: object) -> object:
        if isinstance(response, dict) and isinstance(response.get("content"), list):
            texts = [
                block.get("text")
                for block in response["content"]
                if isinstance(block, dict)
                and block.get("type") == "text"
                and isinstance(block.get("text"), str)
            ]
            if len(texts) != 1:
                raise GatewayProtocolError("MCP response must contain exactly one text block")
            return texts[0]
        content = getattr(response, "content", None)
        if isinstance(content, list):
            texts = [getattr(block, "text", None) for block in content]
            texts = [item for item in texts if isinstance(item, str)]
            if len(texts) != 1:
                raise GatewayProtocolError("MCP response must contain exactly one text block")
            return texts[0]
        return response

    @staticmethod
    def _nonnegative_int(value: object, name: str) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise GatewayProtocolError(f"MCP response has invalid {name}")
        return value
