"""Gateway contract independent of MCP, direct HTTP, and local fixtures."""

from typing import Protocol

from app.contracts.execution import RawSearchResult
from app.contracts.query import CompiledQuery
from app.contracts.semantic import FieldProfileSnapshot, MappingSnapshot
from app.gateway.bindings import GatewayHealth, MappingRequest


class OpenSearchGateway(Protocol):
    async def get_mapping(self, request: MappingRequest) -> MappingSnapshot: ...

    async def execute_search(self, query: CompiledQuery) -> RawSearchResult: ...

    async def health(self) -> GatewayHealth: ...


class SemanticMetadataGateway(Protocol):
    """Administrative discovery surface; never injected into an LLM agent."""

    async def list_indices(self, index_pattern: str) -> tuple[str, ...]: ...

    async def get_mapping(self, request: MappingRequest) -> MappingSnapshot: ...

    async def profile_fields(
        self,
        snapshot: MappingSnapshot,
        *,
        allowed_source_paths: tuple[str, ...],
        max_fields: int = 100,
        sample_value_limit: int = 5,
    ) -> FieldProfileSnapshot: ...
