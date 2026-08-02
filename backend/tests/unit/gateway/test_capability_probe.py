"""MCP capability names and input modes are resolved from configuration."""

from pathlib import Path

from app.gateway.bindings import GatewayBindings, ToolDescriptor
from app.gateway.capability_probe import McpCapabilityProbe

CONFIG = Path(__file__).parents[4] / "config" / "gateway.mcp.yaml"


def _tools(query_dsl_type: str = "object") -> tuple[ToolDescriptor, ...]:
    names = {
        "ListIndexTool": {"properties": {}},
        "IndexMappingTool": {"properties": {"index": {"type": "string"}}},
        "SearchIndexTool": {
            "properties": {
                "index": {"type": "string"},
                "query_dsl": {"type": query_dsl_type},
            }
        },
        "ClusterHealthTool": {"properties": {}},
        "GenericOpenSearchApiTool": {"properties": {}},
    }
    return tuple(ToolDescriptor(name=name, input_schema=schema) for name, schema in names.items())


def test_probe_resolves_required_tools_and_query_object_mode() -> None:
    bindings = GatewayBindings.from_file(CONFIG)
    report = McpCapabilityProbe().probe(bindings, _tools())
    assert report.ready
    assert report.query_dsl_mode == "object"
    assert report.resolved_bindings["execute_search"] == "SearchIndexTool"
    assert report.forbidden_bindings == ()


def test_probe_rejects_missing_required_tool_and_forbidden_binding() -> None:
    bindings = GatewayBindings.from_file(CONFIG)
    unsafe = bindings.model_copy(
        update={
            "tool_bindings": {
                **bindings.tool_bindings,
                "execute_search": bindings.forbidden_tools[0],
            }
        }
    )
    report = McpCapabilityProbe().probe(unsafe, _tools())
    assert not report.ready
    assert report.forbidden_bindings == (bindings.forbidden_tools[0],)
