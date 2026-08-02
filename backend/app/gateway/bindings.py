"""Configured MCP tool bindings and capability report."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field

from app.contracts.common import JsonValue, StrictModel


class MappingRequest(StrictModel):
    dataset_id: str
    indices: tuple[str, ...]


class GatewayHealth(StrictModel):
    ready: bool
    mode: Literal["mock", "mcp", "direct"]
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ToolDescriptor(StrictModel):
    name: str
    input_schema: dict[str, JsonValue]


class GatewayBindings(StrictModel):
    tool_bindings: dict[str, str]
    allowed_capabilities: tuple[str, ...]
    forbidden_tools: tuple[str, ...]

    @classmethod
    def from_file(cls, path: Path) -> GatewayBindings:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        gateway = raw.get("gateway", {}) if isinstance(raw, dict) else {}
        mcp = gateway.get("mcp", {}) if isinstance(gateway, dict) else {}
        return cls.model_validate(
            {
                "tool_bindings": mcp.get("tool_bindings", {}),
                "allowed_capabilities": mcp.get("allowed_capabilities", ()),
                "forbidden_tools": mcp.get("forbidden_tools", ()),
            },
            strict=False,
        )


class McpCapabilityReport(StrictModel):
    ready: bool
    required_capabilities: tuple[str, ...]
    resolved_bindings: dict[str, str]
    missing_capabilities: tuple[str, ...] = ()
    forbidden_bindings: tuple[str, ...] = ()
    query_dsl_mode: Literal["object", "string", "unknown"] = "unknown"
    issues: tuple[str, ...] = ()
