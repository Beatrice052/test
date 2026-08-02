"""Route a half-open business time range to allowlisted monthly indices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from zoneinfo import ZoneInfo

from app.contracts.common import TimeRange
from app.contracts.semantic import CanonicalField, DatasetDefinition, PolicyDefinition


class IndexRoutingError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class IndexRoute:
    indices: tuple[str, ...]
    missing_indices: tuple[str, ...] = ()
    incompatible_indices: tuple[str, ...] = ()


class IndexRouter:
    def __init__(
        self,
        *,
        datasets: tuple[DatasetDefinition, ...],
        policies: tuple[PolicyDefinition, ...],
        fields: tuple[CanonicalField, ...],
    ) -> None:
        self.datasets = {item.dataset_id: item for item in datasets}
        self.policies = {item.policy_id: item for item in policies}
        self.fields = {item.field_id: item for item in fields}

    def route(
        self,
        *,
        dataset_id: str,
        time_range: TimeRange,
        policy_id: str,
        available_indices: tuple[str, ...],
        required_field_ids: tuple[str, ...],
    ) -> IndexRoute:
        try:
            dataset = self.datasets[dataset_id]
            policy = self.policies[policy_id]
        except KeyError as error:
            raise IndexRoutingError(f"unknown dataset or policy: {error.args[0]}") from error
        if dataset_id not in policy.allowed_dataset_ids:
            raise IndexRoutingError(f"dataset is not allowed: {dataset_id}")
        expected = self._monthly_indices(dataset, time_range)
        available = set(available_indices)
        allowed = set(policy.allowed_index_patterns)
        routed: list[str] = []
        missing: list[str] = []
        incompatible: list[str] = []
        for index in expected:
            if index not in allowed:
                raise IndexRoutingError(f"index is outside policy allowlist: {index}")
            if index not in available:
                missing.append(index)
                if dataset.missing_index_policy == "error":
                    raise IndexRoutingError(f"required monthly index is missing: {index}")
                continue
            if any(not self._field_available(field_id, index) for field_id in required_field_ids):
                incompatible.append(index)
                continue
            routed.append(index)
        return IndexRoute(tuple(routed), tuple(missing), tuple(incompatible))

    @staticmethod
    def _monthly_indices(dataset: DatasetDefinition, time_range: TimeRange) -> tuple[str, ...]:
        timezone = ZoneInfo(dataset.default_timezone)
        start = time_range.from_inclusive.astimezone(timezone)
        last = (time_range.to_exclusive - timedelta(microseconds=1)).astimezone(timezone)
        cursor_year, cursor_month = start.year, start.month
        indices: list[str] = []
        while (cursor_year, cursor_month) <= (last.year, last.month):
            indices.append(
                dataset.index_pattern.replace("{YYYY}", f"{cursor_year:04d}").replace(
                    "{MM}", f"{cursor_month:02d}"
                )
            )
            if cursor_month == 12:
                cursor_year, cursor_month = cursor_year + 1, 1
            else:
                cursor_month += 1
        return tuple(indices)

    def _field_available(self, field_id: str, index: str) -> bool:
        field = self.fields.get(field_id)
        return field is not None and index in field.observed_in_indices
