from __future__ import annotations

from typing import Any

import pytest

from app.gateway.mcp import MCPOpenSearchGateway
from app.gateway.models import GatewayCapabilities
from app.query.models import CompiledQuery, Complexity


class FakeAllowedClient:
    def list_indices(self, pattern: str | None = None) -> list[str]:
        return ["tbl_os_sub_message_2026_07", "other_sensitive_index"]

    def get_mapping(self, index: str) -> dict[str, Any]:
        return {"index": index}

    def count(self, index: str, query: dict[str, Any]) -> dict[str, Any]:
        return {"count": 1}

    def search(self, index: str, body: dict[str, Any]) -> dict[str, Any]:
        return {"hits": {"total": {"value": 1, "relation": "eq"}}}

    def msearch(self, requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"hits": {"total": {"value": 1, "relation": "eq"}}} for _ in requests]


def _query(index: str) -> CompiledQuery:
    return CompiledQuery(
        query_id=f"q:{index}",
        logical_query_id="q",
        index=index,
        query_type="count",
        body={"query": {"bool": {"filter": []}}},
        estimated_complexity=Complexity.LOW,
        validation_status="PASSED",
    )


def test_mcp_gateway_filters_index_inventory_and_has_no_generic_surface() -> None:
    gateway = MCPOpenSearchGateway(FakeAllowedClient())

    assert gateway.list_indices() == ["tbl_os_sub_message_2026_07"]
    assert gateway.capabilities().generic_api is False
    assert gateway.capabilities().ppl is False
    assert not hasattr(gateway, "generic_api")
    assert not hasattr(gateway, "ppl_query")


def test_mcp_gateway_rejects_index_outside_allowlist() -> None:
    gateway = MCPOpenSearchGateway(FakeAllowedClient())

    with pytest.raises(ValueError, match="allowlist"):
        gateway.search("other_sensitive_index", {"size": 0})


def test_mcp_gateway_uses_same_deterministic_tool_selection() -> None:
    gateway = MCPOpenSearchGateway(FakeAllowedClient())
    query = _query("tbl_os_sub_message_2026_07")
    multi = [
        query,
        _query("tbl_os_sub_message_2026_08").model_copy(update={"query_id": "q:second"}),
    ]

    assert gateway.plan_execution([query])[0].mcp_tool == "CountTool"
    assert gateway.plan_execution(multi)[0].mcp_tool == "MsearchTool"
    assert len(gateway.execute(multi).results) == 2


def test_mcp_gateway_refuses_capability_escalation() -> None:
    with pytest.raises(ValueError, match="must remain disabled"):
        MCPOpenSearchGateway(
            FakeAllowedClient(),
            capabilities=GatewayCapabilities(generic_api=True),
        )
