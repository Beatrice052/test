"""MCP Adapter probes once, serializes the negotiated DSL mode, and normalizes output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.gateway.bindings import GatewayBindings, ToolDescriptor
from app.gateway.mcp import McpOpenSearchGateway
from tests.unit.gateway.test_mock import compiled_query

CONFIG = Path(__file__).parents[4] / "config" / "gateway.mcp.yaml"


class FakeMcpTransport:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def list_tools(self) -> tuple[ToolDescriptor, ...]:
        bindings = GatewayBindings.from_file(CONFIG)
        return tuple(
            ToolDescriptor(
                name=tool_name,
                input_schema=(
                    {
                        "properties": {
                            "index": {"type": "string"},
                            "query_dsl": {"type": "string"},
                        }
                    }
                    if capability == "execute_search"
                    else {"properties": {"index": {"type": "string"}}}
                ),
            )
            for capability, tool_name in bindings.tool_bindings.items()
            if capability in bindings.allowed_capabilities
        )

    async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
        self.calls.append((name, arguments))
        return self.response


@pytest.mark.asyncio
async def test_mcp_search_string_mode_and_json_content_block() -> None:
    raw = {
        "took": 7,
        "timed_out": False,
        "_shards": {"total": 2, "successful": 2, "skipped": 0, "failed": 0},
        "hits": {"total": {"value": 42}, "hits": []},
        "aggregations": {"dim_00_channel": {"buckets": []}},
    }
    transport = FakeMcpTransport(
        {"content": [{"type": "text", "text": json.dumps(json.dumps(raw))}]}
    )
    gateway = McpOpenSearchGateway(
        transport=transport,
        bindings=GatewayBindings.from_file(CONFIG),
    )
    report = await gateway.probe()
    assert report.ready
    assert report.query_dsl_mode == "string"

    result = await gateway.execute_search(compiled_query())
    _, arguments = transport.calls[0]
    assert isinstance(arguments["query_dsl"], str)
    assert arguments["index"] == "tbl_os_sub_message_2026_07"
    assert result.took_ms == 7
    assert result.hits_total == 42
    assert result.shards.failed == 0
    assert result.gateway_metadata["transport"] == "mcp"


@pytest.mark.asyncio
async def test_mcp_csv_is_normalized_inside_adapter() -> None:
    transport = FakeMcpTransport("channel,count\nSMS,10\nEMAIL,7\n")
    gateway = McpOpenSearchGateway(
        transport=transport,
        bindings=GatewayBindings.from_file(CONFIG),
    )
    await gateway.probe()
    result = await gateway.execute_search(compiled_query())
    assert result.hits == (
        {"channel": "SMS", "count": "10"},
        {"channel": "EMAIL", "count": "7"},
    )
    assert result.gateway_metadata["format"] == "csv"
