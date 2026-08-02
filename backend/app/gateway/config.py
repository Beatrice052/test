"""Load MCP transport configuration without placing credentials in YAML."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import yaml

from app.gateway.bindings import GatewayBindings
from app.gateway.mcp_transport import McpConnectionConfig

INLINE_SECRET_KEYS = frozenset(
    {"api_key", "password", "secret", "token", "authorization", "credential"}
)


def load_mcp_runtime_config(
    path: Path,
) -> tuple[McpConnectionConfig, GatewayBindings]:
    """Resolve transport values and env references from one non-secret config file."""

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("MCP config root must be an object")
    gateway = raw.get("gateway")
    if not isinstance(gateway, Mapping):
        raise ValueError("MCP config gateway section is missing")
    mcp = gateway.get("mcp")
    if not isinstance(mcp, Mapping):
        raise ValueError("MCP config gateway.mcp section is missing")
    inline_keys = INLINE_SECRET_KEYS.intersection(str(key).lower() for key in mcp)
    if inline_keys:
        raise ValueError("MCP credentials must be provided through environment variables")

    endpoint = _optional_string(mcp.get("endpoint"))
    endpoint_env = _optional_string(mcp.get("endpoint_env"))
    if endpoint_env:
        endpoint = os.getenv(endpoint_env) or endpoint

    environment: dict[str, str] = {}
    environment_from_env = mcp.get("environment_from_env", {})
    if not isinstance(environment_from_env, Mapping):
        raise ValueError("gateway.mcp.environment_from_env must be an object")
    for target_name, source_name in environment_from_env.items():
        if not isinstance(target_name, str) or not isinstance(source_name, str):
            raise ValueError("MCP environment references must be strings")
        value = os.getenv(source_name)
        if value is None:
            raise ValueError(f"required environment variable is missing: {source_name}")
        environment[target_name] = value

    raw_args = mcp.get("args", ())
    if not isinstance(raw_args, list | tuple) or not all(
        isinstance(item, str) for item in raw_args
    ):
        raise ValueError("gateway.mcp.args must be a string list")
    cwd = _optional_string(mcp.get("cwd"))
    resolved_cwd = None
    if cwd:
        candidate = Path(cwd)
        resolved_cwd = candidate if candidate.is_absolute() else (path.parent / candidate).resolve()

    transport = McpConnectionConfig.model_validate(
        {
            "transport": str(mcp.get("transport", "streamable_http")),
            "endpoint": endpoint,
            "command": _optional_string(mcp.get("command")),
            "args": tuple(cast(list[str] | tuple[str, ...], raw_args)),
            "cwd": resolved_cwd,
            "environment": environment or None,
            "call_timeout_seconds": float(mcp.get("call_timeout_seconds", 35)),
        },
        strict=True,
    )
    return transport, GatewayBindings.from_file(path)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("MCP config string value has invalid type")
    stripped = value.strip()
    return stripped or None
