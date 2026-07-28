from __future__ import annotations

from datetime import datetime, timedelta

from app.query.models import IndexResolution
from app.semantic.models import QueryPolicy


class IndexResolutionError(ValueError):
    pass


class MonthlyIndexResolver:
    def __init__(self, policy: QueryPolicy) -> None:
        self.policy = policy

    def resolve(
        self,
        start: datetime,
        end: datetime,
        *,
        available_indices: set[str] | None = None,
    ) -> IndexResolution:
        if start.tzinfo is None or end.tzinfo is None:
            raise IndexResolutionError("time range must be timezone-aware")
        if start >= end:
            raise IndexResolutionError("time range must satisfy start < end")
        if end - start > timedelta(days=self.policy.max_time_range_days):
            raise IndexResolutionError("time range exceeds policy")

        final_instant = end - timedelta(microseconds=1)
        cursor = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        final_month = final_instant.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        indices: list[str] = []
        while cursor <= final_month:
            indices.append(
                self.policy.index_pattern.format(
                    yyyy=f"{cursor.year:04d}", mm=f"{cursor.month:02d}"
                )
            )
            cursor = self._next_month(cursor)
        if len(indices) > self.policy.max_month_partitions:
            raise IndexResolutionError("month partition count exceeds policy")

        missing = (
            [index for index in indices if index not in available_indices]
            if available_indices is not None
            else []
        )
        return IndexResolution(indices=indices, missing_indices=missing)

    @staticmethod
    def _next_month(value: datetime) -> datetime:
        if value.month == 12:
            return value.replace(year=value.year + 1, month=1)
        return value.replace(month=value.month + 1)
