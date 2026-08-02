"""Validate the normalized Gateway envelope before business bucket processing."""

from dataclasses import dataclass

from app.contracts.execution import RawSearchResult
from app.contracts.query import CompiledQuery


class ResultParseError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ParsedSearchResult:
    query: CompiledQuery
    raw: RawSearchResult


class RawResultParser:
    """Check cross-object identity and outer response invariants only."""

    def parse(self, query: CompiledQuery, raw: RawSearchResult) -> ParsedSearchResult:
        if raw.query_id != query.object_id:
            raise ResultParseError("raw result belongs to another compiled query")
        if raw.shards.successful + raw.shards.skipped + raw.shards.failed > raw.shards.total:
            raise ResultParseError("shard summary exceeds total shards")
        if query.semantics.bucket_path and not raw.aggregations:
            raise ResultParseError("aggregation query returned no aggregations")
        return ParsedSearchResult(query=query, raw=raw)
