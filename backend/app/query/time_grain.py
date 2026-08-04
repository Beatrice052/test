"""Single deterministic mapping from logical time grain to OpenSearch intervals."""

from __future__ import annotations

from datetime import timedelta
from math import ceil

from app.contracts.common import TimeRange

CALENDAR_INTERVALS = ("minute", "hour", "day", "week", "month", "quarter", "year")


class TimeGrainError(ValueError):
    pass


def resolve_calendar_interval(grain: tuple[str, ...]) -> str:
    """Resolve exactly one governed time token, retaining daily legacy semantics."""

    selected = tuple(dict.fromkeys(item for item in grain if item in CALENDAR_INTERVALS))
    if len(selected) > 1:
        raise TimeGrainError(f"query grain contains conflicting time intervals: {selected}")
    return selected[0] if selected else "day"


def time_bucket_count(time_range: TimeRange, interval: str) -> int:
    start = time_range.from_inclusive
    end = time_range.to_exclusive
    seconds = (end - start).total_seconds()
    if interval == "minute":
        return max(1, ceil(seconds / 60))
    if interval == "hour":
        return max(1, ceil(seconds / 3_600))
    if interval == "day":
        return max(1, ceil(seconds / 86_400))
    if interval == "week":
        return max(1, ceil(seconds / (7 * 86_400)))
    last = end - timedelta(microseconds=1)
    if interval == "month":
        return max(1, (last.year - start.year) * 12 + last.month - start.month + 1)
    if interval == "quarter":
        start_quarter = start.year * 4 + (start.month - 1) // 3
        last_quarter = last.year * 4 + (last.month - 1) // 3
        return max(1, last_quarter - start_quarter + 1)
    if interval == "year":
        return max(1, last.year - start.year + 1)
    raise TimeGrainError(f"unsupported calendar interval: {interval}")
