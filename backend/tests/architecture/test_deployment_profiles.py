"""Deployment profiles are explicit, credential-free, and wired to their adapters."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def _compose() -> dict[str, object]:
    loaded = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_compose_exposes_exact_mock_local_os_and_mcp_profiles() -> None:
    services = _compose()["services"]
    assert isinstance(services, dict)
    profiles = {
        profile
        for service in services.values()
        if isinstance(service, dict)
        for profile in service.get("profiles", [])
    }
    assert profiles == {"mock", "local-os", "mcp"}


def test_mock_profile_has_no_key_or_external_dependency() -> None:
    services = _compose()["services"]
    assert isinstance(services, dict)
    backend = services["backend-mock"]
    assert isinstance(backend, dict)
    environment = backend["environment"]
    assert environment == {
        "APP_ENV": "mock",
        "CHATBI_IDENTITY_MODE": "mock",
        "CHATBI_LLM_MODE": "rule_based",
        "CHATBI_GATEWAY_MODE": "mock",
    }
    assert "OPENSEARCH_MCP_ENDPOINT" not in environment
    assert "CHATBI_LLM_API_KEY" not in environment


def test_local_os_routes_application_through_read_only_official_mcp() -> None:
    services = _compose()["services"]
    assert isinstance(services, dict)
    assert {"opensearch", "fixture-loader", "opensearch-mcp"}.issubset(services)
    backend = services["backend-local-os"]
    mcp = services["opensearch-mcp"]
    assert isinstance(backend, dict) and isinstance(mcp, dict)
    assert backend["environment"]["CHATBI_GATEWAY_MODE"] == "mcp"
    assert backend["environment"]["CHATBI_IDENTITY_MODE"] == "mock"
    assert backend["environment"]["OPENSEARCH_MCP_ENDPOINT"].endswith("/mcp")
    mcp_environment = mcp["environment"]
    assert mcp_environment["OPENSEARCH_SETTINGS_ALLOW_WRITE"] == "false"
    assert "GenericOpenSearchApiTool" in mcp_environment["OPENSEARCH_DISABLED_TOOLS"]
    assert "PPLQueryTool" in mcp_environment["OPENSEARCH_DISABLED_TOOLS"]
    assert (ROOT / "docker" / "mcp" / "uv.lock").is_file()


def test_mcp_profile_reads_runtime_values_only_from_environment() -> None:
    services = _compose()["services"]
    assert isinstance(services, dict)
    backend = services["backend-mcp"]
    assert isinstance(backend, dict)
    environment = backend["environment"]
    assert environment["CHATBI_GATEWAY_MODE"] == "mcp"
    assert environment["CHATBI_IDENTITY_MODE"] == "trusted_headers"
    assert environment["OPENSEARCH_MCP_ENDPOINT"] == "${OPENSEARCH_MCP_ENDPOINT:-}"
    assert environment["CHATBI_LLM_API_KEY"] == "${CHATBI_LLM_API_KEY:-}"
    assert environment["CHATBI_LLM_MODE"] == "${CHATBI_LLM_MODE:-openai_compatible}"
    assert environment["CHATBI_SEMANTIC_PACKAGE_DIR"].endswith("compiled-semantic/internal}")
    assert environment["CHATBI_SEMANTIC_INPUT_DIR"].endswith("semantic-input/internal}")


def test_frontend_proxy_does_not_buffer_sse_progress() -> None:
    nginx = (ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    assert "proxy_http_version 1.1;" in nginx
    assert "proxy_buffering off;" in nginx
    assert "proxy_cache off;" in nginx
    assert "proxy_read_timeout 600s;" in nginx
    assert "add_header X-Accel-Buffering no;" in nginx
