"""Deterministic fingerprint-addressed OpenSearch Gateway with fault injection."""

from __future__ import annotations

from collections import Counter, defaultdict, deque

from app.contracts.execution import RawSearchResult
from app.contracts.query import CompiledQuery
from app.contracts.semantic import MappingSnapshot
from app.gateway.bindings import GatewayHealth, MappingRequest
from app.gateway.errors import GatewayProtocolError


class MockOpenSearchGateway:
    def __init__(self) -> None:
        self._responses: dict[str, deque[RawSearchResult | BaseException]] = defaultdict(deque)
        self._mappings: dict[str, MappingSnapshot] = {}
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

    def is_registered(self, query_fingerprint: str) -> bool:
        return bool(self._responses.get(query_fingerprint))

    async def get_mapping(self, request: MappingRequest) -> MappingSnapshot:
        try:
            return self._mappings[request.dataset_id]
        except KeyError as error:
            raise GatewayProtocolError(
                f"Mock mapping is not registered: {request.dataset_id}"
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
