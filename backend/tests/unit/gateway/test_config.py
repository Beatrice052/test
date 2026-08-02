"""MCP runtime config resolves env references and rejects inline secrets."""

from pathlib import Path

import pytest

from app.gateway.config import load_mcp_runtime_config


def test_loads_endpoint_and_stdio_environment_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MCP_URL", "https://mcp.internal.example/mcp")
    monkeypatch.setenv("OS_PASSWORD", "runtime-only")
    config = tmp_path / "internal.yaml"
    config.write_text(
        """
gateway:
  mcp:
    transport: streamable_http
    endpoint_env: MCP_URL
    environment_from_env:
      OPENSEARCH_PASSWORD: OS_PASSWORD
    tool_bindings:
      execute_search: SearchIndexTool
    allowed_capabilities: [execute_search]
    forbidden_tools: [GenericOpenSearchApiTool]
""".strip(),
        encoding="utf-8",
    )

    transport, bindings = load_mcp_runtime_config(config)

    assert transport.endpoint == "https://mcp.internal.example/mcp"
    assert transport.environment == {"OPENSEARCH_PASSWORD": "runtime-only"}
    assert bindings.tool_bindings["execute_search"] == "SearchIndexTool"


def test_rejects_inline_secret(tmp_path: Path) -> None:
    config = tmp_path / "unsafe.yaml"
    config.write_text(
        """
gateway:
  mcp:
    transport: streamable_http
    endpoint: https://mcp.internal.example/mcp
    password: should-not-be-here
    tool_bindings: {}
    allowed_capabilities: []
    forbidden_tools: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="environment variables"):
        load_mcp_runtime_config(config)
