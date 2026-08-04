"""Deterministic fingerprint-addressed OpenSearch Gateway with fault injection."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from fnmatch import fnmatchcase

from app.contracts.execution import RawSearchResult
from app.contracts.query import CompiledQuery
from app.contracts.semantic import FieldProfileSnapshot, MappingSnapshot
from app.gateway.bindings import GatewayHealth, MappingRequest
from app.gateway.errors import GatewayProtocolError


class MockOpenSearchGateway:
    def __init__(self) -> None:
        self._responses: dict[str, deque[RawSearchResult | BaseException]] = defaultdict(deque)
        self._mappings: dict[str, MappingSnapshot] = {}
        self._profiles: dict[str, FieldProfileSnapshot] = {}
        self.calls: Counter[str] = Counter()
        self.total_calls = 0

    def register(
        self,
        query_fingerprint: str,
        *responses: RawSearchResult | BaseException,
    ) -> None:
        if not responses:
            raise ValueError("at least one Mock response is required")
        self._responses[query_fingerprint].extend(responses)

    def register_mapping(self, snapshot: MappingSnapshot) -> None:
        self._mappings[snapshot.dataset_id] = snapshot

    def register_field_profile(self, snapshot: FieldProfileSnapshot) -> None:
        self._profiles[snapshot.dataset_id] = snapshot

    def is_registered(self, query_fingerprint: str) -> bool:
        return bool(self._responses.get(query_fingerprint))

    async def get_mapping(self, request: MappingRequest) -> MappingSnapshot:
        try:
            return self._mappings[request.dataset_id]
        except KeyError as error:
            raise GatewayProtocolError(
                f"Mock mapping is not registered: {request.dataset_id}"
            ) from error

    async def list_indices(self, index_pattern: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    index
                    for snapshot in self._mappings.values()
                    for index in snapshot.indices
                    if fnmatchcase(index, index_pattern)
                }
            )
        )

    async def profile_fields(
        self,
        snapshot: MappingSnapshot,
        *,
        allowed_source_paths: tuple[str, ...],
        max_fields: int = 100,
        sample_value_limit: int = 5,
    ) -> FieldProfileSnapshot:
        del allowed_source_paths, max_fields, sample_value_limit
        try:
            return self._profiles[snapshot.dataset_id]
        except KeyError as error:
            raise GatewayProtocolError(
                f"Mock field profile is not registered: {snapshot.dataset_id}"
            ) from error

    async def execute_search(self, query: CompiledQuery) -> RawSearchResult:
        self.calls[query.query_fingerprint] += 1
        self.total_calls += 1
        queue = self._responses.get(query.query_fingerprint)
        if not queue:
            raise GatewayProtocolError(
                f"Mock response is not registered: {query.query_fingerprint}"
            )
        response = queue[0] if len(queue) == 1 else queue.popleft()
        if isinstance(response, BaseException):
            raise response
        return response

    async def health(self) -> GatewayHealth:
        return GatewayHealth(ready=True, mode="mock", details={"fixtures": len(self._responses)})
