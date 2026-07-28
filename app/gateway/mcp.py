from __future__ import annotations

import re
from typing import Any, Protocol

from app.gateway.execution import execute_queries, plan_execution
from app.gateway.models import (
    ExecutionBundle,
    ExecutionStep,
    GatewayCapabilities,
)
from app.query.models import CompiledQuery


class AllowedMCPToolClient(Protocol):
    """Narrow client contract; generic OpenSearch and PPL are intentionally absent."""

    def list_indices(self, pattern: str | None = None) -> list[str]: ...

    def get_mapping(self, index: str) -> dict[str, Any]: ...

    def count(self, index: str, query: dict[str, Any]) -> dict[str, Any]: ...

    def search(self, index: str, body: dict[str, Any]) -> dict[str, Any]: ...

    def msearch(self, requests: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


class MCPOpenSearchGateway:
    """Internal-network adapter seam for the five explicitly allowed capabilities.

    The external project intentionally does not instantiate this class. An
    internal bootstrap supplies an authenticated AllowedMCPToolClient, while the
    Agent, QueryPlan, API and front end remain unchanged.
    """

    def __init__(
        self,
        client: AllowedMCPToolClient,
        *,
        index_pattern: str = "tbl_os_sub_message_{yyyy}_{mm}",
        capabilities: GatewayCapabilities | None = None,
    ) -> None:
        self.client = client
        pattern = re.escape(index_pattern)
        pattern = pattern.replace(re.escape("{yyyy}"), r"\d{4}")
        pattern = pattern.replace(re.escape("{mm}"), r"(0[1-9]|1[0-2])")
        self._index_regex = re.compile(f"^{pattern}$")
        self._capabilities = capabilities or GatewayCapabilities()
        if self._capabilities.generic_api or self._capabilities.ppl:
            raise ValueError("generic API and PPL capabilities must remain disabled")

    def capabilities(self) -> GatewayCapabilities:
        return self._capabilities.model_copy(deep=True)

    def list_indices(self, pattern: str | None = None) -> list[str]:
        return sorted(
            index
            for index in self.client.list_indices(pattern)
            if self._index_regex.fullmatch(index)
        )

    def get_mapping(self, index: str) -> dict[str, Any]:
        self._assert_index(index)
        return self.client.get_mapping(index)

    def count(self, index: str, query: dict[str, Any]) -> dict[str, Any]:
        self._assert_index(index)
        return self.client.count(index, query)

    def search(self, index: str, body: dict[str, Any]) -> dict[str, Any]:
        self._assert_index(index)
        return self.client.search(index, body)

    def msearch(self, requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for request in requests:
            self._assert_index(str(request["index"]))
        return self.client.msearch(requests)

    def plan_execution(self, queries: list[CompiledQuery]) -> list[ExecutionStep]:
        return plan_execution(queries, self._capabilities)

    def execute(self, queries: list[CompiledQuery]) -> ExecutionBundle:
        return execute_queries(self, queries, self._capabilities)

    def _assert_index(self, index: str) -> None:
        if not self._index_regex.fullmatch(index):
            raise ValueError("index is outside the configured allowlist")
