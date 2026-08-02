"""Gateway contract independent of MCP, direct HTTP, and local fixtures."""

from typing import Protocol

from app.contracts.execution import RawSearchResult
from app.contracts.query import CompiledQuery
from app.contracts.semantic import MappingSnapshot
from app.gateway.bindings import GatewayHealth, MappingRequest


class OpenSearchGateway(Protocol):
    async def get_mapping(self, request: MappingRequest) -> MappingSnapshot: ...

    async def execute_search(self, query: CompiledQuery) -> RawSearchResult: ...

    async def health(self) -> GatewayHealth: ...
