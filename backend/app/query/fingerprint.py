"""Canonical query identities used for idempotent execution and fixtures."""

from app.contracts.common import semantic_hash
from app.contracts.query import QuerySemantics


def query_fingerprint(
    *,
    indices: tuple[str, ...],
    query_dsl: dict[str, object],
    semantics: QuerySemantics,
) -> str:
    return semantic_hash(
        {
            "indices": indices,
            "query_dsl": query_dsl,
            "semantics": semantics.model_dump(mode="json"),
        }
    )
