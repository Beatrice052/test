"""Closed query AST created only from validated IDs by deterministic code."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class FilterNode:
    kind: Literal["eq", "in", "range", "exists", "not"]
    field_id: str
    values: tuple[str | int | float | bool, ...] = ()


@dataclass(frozen=True, slots=True)
class BucketNode:
    name: str
    kind: Literal["terms", "composite", "date_histogram"]
    field_id: str
    size: int | None = None
    interval: str | None = None
    time_zone: str | None = None


@dataclass(frozen=True, slots=True)
class MeasureNode:
    name: str
    kind: Literal[
        "document_count",
        "value_count",
        "cardinality",
        "sum",
        "avg",
        "min",
        "max",
        "stats",
        "extended_stats",
        "percentiles",
    ]
    metric_id: str
    field_id: str | None = None


@dataclass(frozen=True, slots=True)
class QueryAst:
    filters: tuple[FilterNode, ...]
    buckets: tuple[BucketNode, ...]
    measures: tuple[MeasureNode, ...]
