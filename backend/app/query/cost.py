"""Query budget policy that callers and LLMs can only shrink."""

from dataclasses import dataclass


class QueryBudgetError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class QueryBudget:
    max_queries_per_turn: int = 3
    max_dependent_query_rounds: int = 1
    max_total_buckets: int = 5000
    max_composite_pages: int = 20
    max_raw_response_bytes: int = 10_000_000
    max_detail_hits: int = 100
    query_timeout_seconds: int = 30
    turn_timeout_seconds: int = 90
    max_parallel_queries: int = 3

    def validate(self, *, query_count: int, total_buckets: int, timeout_ms: int) -> None:
        if query_count > self.max_queries_per_turn:
            raise QueryBudgetError("query count exceeds policy")
        if total_buckets > self.max_total_buckets:
            raise QueryBudgetError("estimated bucket count exceeds policy")
        if timeout_ms > self.query_timeout_seconds * 1000:
            raise QueryBudgetError("query timeout exceeds policy")
