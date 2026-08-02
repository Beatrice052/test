"""Resolve configured capabilities once at startup, never inside Agent code."""

from typing import Literal

from app.gateway.bindings import (
    GatewayBindings,
    McpCapabilityReport,
    ToolDescriptor,
)


class McpCapabilityProbe:
    def probe(
        self, bindings: GatewayBindings, tools: tuple[ToolDescriptor, ...]
    ) -> McpCapabilityReport:
        by_name = {tool.name: tool for tool in tools}
        required = bindings.allowed_capabilities
        resolved: dict[str, str] = {}
        missing: list[str] = []
        forbidden: list[str] = []
        issues: list[str] = []
        for capability in required:
            tool_name = bindings.tool_bindings.get(capability)
            if tool_name is None or tool_name not in by_name:
                missing.append(capability)
                continue
            if tool_name in bindings.forbidden_tools:
                forbidden.append(tool_name)
                continue
            resolved[capability] = tool_name

        query_dsl_mode: Literal["object", "string", "unknown"] = "unknown"
        search_name = resolved.get("execute_search")
        if search_name is not None:
            schema = by_name[search_name].input_schema
            properties = schema.get("properties", {})
            query_schema = properties.get("query_dsl", {}) if isinstance(properties, dict) else {}
            schema_type = query_schema.get("type") if isinstance(query_schema, dict) else None
            if schema_type in {"object", "string"}:
                query_dsl_mode = schema_type
            else:
                issues.append("execute_search.query_dsl type is not object or string")
            if not isinstance(properties, dict) or "index" not in properties:
                issues.append("execute_search.index input is missing")
        ready = not missing and not forbidden and not issues
        return McpCapabilityReport(
            ready=ready,
            required_capabilities=required,
            resolved_bindings=resolved,
            missing_capabilities=tuple(missing),
            forbidden_bindings=tuple(forbidden),
            query_dsl_mode=query_dsl_mode,
            issues=tuple(issues),
        )
