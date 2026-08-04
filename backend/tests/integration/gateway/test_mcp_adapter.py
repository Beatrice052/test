"""MCP Adapter probes once, serializes the negotiated DSL mode, and normalizes output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.gateway.bindings import GatewayBindings, ToolDescriptor
from app.gateway.mcp import McpOpenSearchGateway
from app.semantic.mapping import flatten_mapping_snapshot
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


class MetadataMcpTransport(FakeMcpTransport):
    async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
        self.calls.append((name, arguments))
        if name == "ListIndexTool":
            return {
                "indices": [
                    {"index": "tbl_os_sub_message_2026_06"},
                    {"index": "unrelated_index"},
                    {"index": "tbl_os_sub_message_2026_07"},
                ]
            }
        if name == "SearchIndexTool":
            return {
                "hits": {"total": {"value": 100}, "hits": []},
                "aggregations": {
                    "profile_000": {
                        "doc_count": 100,
                        "cardinality": {"value": 3},
                        "non_null": {"value": 95},
                        "missing": {"doc_count": 5},
                        "sample_values": {
                            "buckets": [
                                {"key": "SMS", "doc_count": 60},
                                {"key": "EMAIL", "doc_count": 35},
                            ]
                        },
                    }
                },
            }
        return self.response


@pytest.mark.asyncio
async def test_mcp_discovers_indices_and_builds_bounded_aggregate_profile() -> None:
    raw_mapping = {
        "captured_at": "2026-08-04T00:00:00Z",
        "indices": {
            "tbl_os_sub_message_2026_06": {
                "mappings": {"properties": {"channel": {"type": "keyword"}}}
            },
            "tbl_os_sub_message_2026_07": {
                "mappings": {"properties": {"channel": {"type": "keyword"}}}
            },
        },
    }
    mapping = flatten_mapping_snapshot(raw_mapping, dataset_id="sub_message")
    transport = MetadataMcpTransport({})
    gateway = McpOpenSearchGateway(
        transport=transport,
        bindings=GatewayBindings.from_file(CONFIG),
    )
    await gateway.probe()

    indices = await gateway.list_indices("tbl_os_sub_message_2026_*")
    profile = await gateway.profile_fields(
        mapping,
        allowed_source_paths=("channel",),
        sample_value_limit=2,
    )

    assert indices == (
        "tbl_os_sub_message_2026_06",
        "tbl_os_sub_message_2026_07",
    )
    assert len(profile.fields) == 1
    assert profile.fields[0].cardinality_estimate == 3
    assert profile.fields[0].missing_count == 5
    assert profile.fields[0].sample_values == ("SMS", "EMAIL")
    _, search_arguments = transport.calls[-1]
    query = json.loads(str(search_arguments["query_dsl"]))
    assert query["size"] == 0
    assert "_source" not in query
    assert profile.provenance.metadata["raw_size_bytes"] > 0
