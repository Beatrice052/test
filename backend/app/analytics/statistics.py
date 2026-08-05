"""Whitelisted exploratory statistical methods over validated datasets."""

from __future__ import annotations

import statistics
from collections.abc import Mapping
from typing import Protocol

from app.contracts.common import JsonValue, semantic_hash
from app.contracts.dataset import TabularDataset
from app.contracts.insight import StatisticalResult


class StatisticalMethod(Protocol):
    method_id: str
    version: str

    def compute(
        self, dataset: TabularDataset, params: Mapping[str, JsonValue]
    ) -> StatisticalResult: ...


def _numeric_rows(dataset: TabularDataset, column: str) -> list[tuple[str, float]]:
    return [
        (row.row_id, float(value))
        for row in dataset.rows
        if isinstance((value := row.values.get(column)), int | float)
        and not isinstance(value, bool)
    ]


class RankMethod:
    method_id = "rank"
    version = "v1"

    def compute(
        self, dataset: TabularDataset, params: Mapping[str, JsonValue]
    ) -> StatisticalResult:
        column = str(params.get("column", "record_count"))
        raw_n = params.get("n", 5)
        n = int(raw_n) if isinstance(raw_n, int | float | str) else 5
        rows = _numeric_rows(dataset, column)
        if len(rows) < 2:
            return StatisticalResult(
                method_id=self.method_id,
                version=self.version,
                applicability="NOT_APPLICABLE",
                sample_size=len(rows),
                warnings=("rank requires at least two numeric rows",),
            )
        ranked = sorted(rows, key=lambda item: (-item[1], item[0]))[:n]
        return StatisticalResult(
            method_id=self.method_id,
            version=self.version,
            applicability="APPLICABLE",
            sample_size=len(rows),
            values={
                "column": column,
                "top": [
                    {"row_id": row_id, "rank": index, "value": value}
                    for index, (row_id, value) in enumerate(ranked, start=1)
                ],
            },
        )


class ContributionMethod:
    method_id = "contribution"
    version = "v1"

    def compute(
        self, dataset: TabularDataset, params: Mapping[str, JsonValue]
    ) -> StatisticalResult:
        column = str(params.get("column", "record_count"))
        rows = _numeric_rows(dataset, column)
        total = sum(value for _, value in rows)
        if len(rows) < 2 or total == 0:
            return StatisticalResult(
                method_id=self.method_id,
                version=self.version,
                applicability="NOT_APPLICABLE",
                sample_size=len(rows),
                warnings=("contribution requires at least two rows and a non-zero total",),
            )
        return StatisticalResult(
            method_id=self.method_id,
            version=self.version,
            applicability="APPLICABLE",
            sample_size=len(rows),
            values={
                "column": column,
                "total": total,
                "shares": [
                    {"row_id": row_id, "share": round(value / total, 6)} for row_id, value in rows
                ],
            },
        )


class WithinGroupContributionMethod:
    method_id = "within_group_contribution"
    version = "v1"

    def compute(
        self, dataset: TabularDataset, params: Mapping[str, JsonValue]
    ) -> StatisticalResult:
        column = str(params.get("column", "record_count"))
        category_column = str(params.get("category_column", ""))
        raw_partitions = params.get("partition_columns", [])
        partition_columns = (
            tuple(str(item) for item in raw_partitions if isinstance(item, str))
            if isinstance(raw_partitions, list)
            else ()
        )
        if not category_column or not dataset.complete:
            return StatisticalResult(
                method_id=self.method_id,
                version=self.version,
                applicability="NOT_APPLICABLE",
                sample_size=len(dataset.rows),
                warnings=(
                    "within-group contribution requires a category and complete distribution",
                ),
            )
        groups: dict[tuple[JsonValue, ...], list[tuple[str, JsonValue, float]]] = {}
        for row in dataset.rows:
            value = row.values.get(column)
            if not isinstance(value, int | float) or isinstance(value, bool):
                continue
            partition = tuple(row.values.get(item) for item in partition_columns)
            groups.setdefault(partition, []).append(
                (row.row_id, row.values.get(category_column), float(value))
            )
        output: list[dict[str, JsonValue]] = []
        for partition, rows in sorted(groups.items(), key=lambda item: semantic_hash(item[0])):
            total = sum(value for _, _, value in rows)
            if total == 0:
                continue
            partition_values = dict(zip(partition_columns, partition, strict=True))
            output.extend(
                {
                    "partition": partition_values,
                    "row_id": row_id,
                    "category": category,
                    "value": value,
                    "within_group_share": value / total,
                }
                for row_id, category, value in rows
            )
        if len(output) < 2:
            return StatisticalResult(
                method_id=self.method_id,
                version=self.version,
                applicability="NOT_APPLICABLE",
                sample_size=len(output),
                warnings=("within-group contribution requires at least two non-zero rows",),
            )
        return StatisticalResult(
            method_id=self.method_id,
            version=self.version,
            applicability="APPLICABLE",
            sample_size=len(output),
            values={
                "column": column,
                "partition_columns": list(partition_columns),
                "category_column": category_column,
                "rows": output,
            },
        )


class MeanMedianMethod:
    method_id = "mean_median"
    version = "v1"

    def compute(
        self, dataset: TabularDataset, params: Mapping[str, JsonValue]
    ) -> StatisticalResult:
        column = str(params.get("column", "record_count"))
        rows = _numeric_rows(dataset, column)
        if not rows:
            return StatisticalResult(
                method_id=self.method_id,
                version=self.version,
                applicability="NOT_APPLICABLE",
                sample_size=0,
                warnings=("mean/median requires at least one numeric row",),
            )
        values = [value for _, value in rows]
        return StatisticalResult(
            method_id=self.method_id,
            version=self.version,
            applicability="APPLICABLE",
            sample_size=len(values),
            values={
                "column": column,
                "mean": statistics.fmean(values),
                "median": statistics.median(values),
                "minimum": min(values),
                "maximum": max(values),
            },
        )


class PercentileMethod:
    method_id = "percentiles"
    version = "v1"

    def compute(
        self, dataset: TabularDataset, params: Mapping[str, JsonValue]
    ) -> StatisticalResult:
        column = str(params.get("column", "record_count"))
        values = sorted(value for _, value in _numeric_rows(dataset, column))
        if not values:
            return StatisticalResult(
                method_id=self.method_id,
                version=self.version,
                applicability="NOT_APPLICABLE",
                sample_size=0,
                warnings=("percentiles require at least one numeric row",),
            )
        requested = params.get("percentiles", [50, 95, 99])
        percentiles = (
            [float(item) for item in requested if isinstance(item, int | float)]
            if isinstance(requested, list)
            else [50.0, 95.0, 99.0]
        )
        return StatisticalResult(
            method_id=self.method_id,
            version=self.version,
            applicability="APPLICABLE",
            sample_size=len(values),
            values={
                "column": column,
                "percentiles": {
                    self._percentile_label(item): self._percentile(values, item)
                    for item in percentiles
                    if 0 <= item <= 100
                },
            },
        )

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if len(values) == 1:
            return values[0]
        position = (len(values) - 1) * percentile / 100
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)
        fraction = position - lower
        return values[lower] + (values[upper] - values[lower]) * fraction

    @staticmethod
    def _percentile_label(percentile: float) -> str:
        label = str(int(percentile)) if percentile.is_integer() else format(percentile, "g")
        return f"p{label}"


class StdCvMethod:
    method_id = "std_cv"
    version = "v1"
    minimum_rows = 7

    def compute(
        self, dataset: TabularDataset, params: Mapping[str, JsonValue]
    ) -> StatisticalResult:
        column = str(params.get("column", "record_count"))
        values = [value for _, value in _numeric_rows(dataset, column)]
        if len(values) < self.minimum_rows:
            return StatisticalResult(
                method_id=self.method_id,
                version=self.version,
                applicability="NOT_APPLICABLE",
                sample_size=len(values),
                warnings=(f"std/CV requires at least {self.minimum_rows} rows",),
            )
        mean = statistics.fmean(values)
        standard_deviation = statistics.stdev(values)
        return StatisticalResult(
            method_id=self.method_id,
            version=self.version,
            applicability="APPLICABLE",
            sample_size=len(values),
            values={
                "column": column,
                "mean": mean,
                "standard_deviation": standard_deviation,
                "coefficient_of_variation": (None if mean == 0 else standard_deviation / abs(mean)),
            },
            warnings=("CV is undefined because the mean is zero",) if mean == 0 else (),
        )


class MovingAverageMethod:
    method_id = "moving_average"
    version = "v1"

    def compute(
        self, dataset: TabularDataset, params: Mapping[str, JsonValue]
    ) -> StatisticalResult:
        column = str(params.get("column", "record_count"))
        time_column = str(params.get("time_column", ""))
        raw_window = params.get("window", 7)
        window = int(raw_window) if isinstance(raw_window, int | float) else 7
        points = sorted(
            (
                str(time_value),
                row.row_id,
                float(value),
            )
            for row in dataset.rows
            if (time_value := row.values.get(time_column)) is not None
            and isinstance((value := row.values.get(column)), int | float)
            and not isinstance(value, bool)
        )
        if window < 2 or len(points) < window:
            return StatisticalResult(
                method_id=self.method_id,
                version=self.version,
                applicability="NOT_APPLICABLE",
                sample_size=len(points),
                warnings=(f"moving average requires at least {max(2, window)} ordered rows",),
            )
        output = []
        for index in range(window - 1, len(points)):
            current = points[index]
            window_points = points[index - window + 1 : index + 1]
            average = statistics.fmean(item[2] for item in window_points)
            output.append(
                {
                    "time": current[0],
                    "row_id": current[1],
                    "value": current[2],
                    "moving_average": average,
                }
            )
        return StatisticalResult(
            method_id=self.method_id,
            version=self.version,
            applicability="APPLICABLE",
            sample_size=len(points),
            values={
                "column": column,
                "time_column": time_column,
                "window": window,
                "points": output,
            },
        )


class HhiMethod:
    method_id = "hhi"
    version = "v1"

    def compute(
        self, dataset: TabularDataset, params: Mapping[str, JsonValue]
    ) -> StatisticalResult:
        column = str(params.get("column", "record_count"))
        rows = _numeric_rows(dataset, column)
        total = sum(value for _, value in rows)
        if not dataset.complete or len(rows) < 2 or total <= 0:
            return StatisticalResult(
                method_id=self.method_id,
                version=self.version,
                applicability="NOT_APPLICABLE",
                sample_size=len(rows),
                warnings=("HHI requires a complete positive distribution with at least two rows",),
            )
        return StatisticalResult(
            method_id=self.method_id,
            version=self.version,
            applicability="APPLICABLE",
            sample_size=len(rows),
            values={
                "column": column,
                "hhi": sum((value / total) ** 2 for _, value in rows),
                "total": total,
            },
        )


class ParetoMethod:
    method_id = "pareto"
    version = "v1"

    def compute(
        self, dataset: TabularDataset, params: Mapping[str, JsonValue]
    ) -> StatisticalResult:
        column = str(params.get("column", "record_count"))
        rows = sorted(_numeric_rows(dataset, column), key=lambda item: (-item[1], item[0]))
        total = sum(value for _, value in rows)
        if not dataset.complete or len(rows) < 2 or total <= 0:
            return StatisticalResult(
                method_id=self.method_id,
                version=self.version,
                applicability="NOT_APPLICABLE",
                sample_size=len(rows),
                warnings=("Pareto requires a complete positive distribution",),
            )
        running = 0.0
        points = []
        for row_id, value in rows:
            running += value
            points.append(
                {
                    "row_id": row_id,
                    "value": value,
                    "share": value / total,
                    "cumulative_share": running / total,
                }
            )
        return StatisticalResult(
            method_id=self.method_id,
            version=self.version,
            applicability="APPLICABLE",
            sample_size=len(rows),
            values={"column": column, "total": total, "points": points},
        )


class PeakToAverageMethod:
    method_id = "peak_to_average"
    version = "v1"

    def compute(
        self, dataset: TabularDataset, params: Mapping[str, JsonValue]
    ) -> StatisticalResult:
        column = str(params.get("column", "record_count"))
        rows = _numeric_rows(dataset, column)
        if not rows:
            return StatisticalResult(
                method_id=self.method_id,
                version=self.version,
                applicability="NOT_APPLICABLE",
                sample_size=0,
                warnings=("peak-to-average requires numeric rows",),
            )
        average = statistics.fmean(value for _, value in rows)
        peak_row_id, peak = max(rows, key=lambda item: (item[1], item[0]))
        if average == 0:
            return StatisticalResult(
                method_id=self.method_id,
                version=self.version,
                applicability="NOT_APPLICABLE",
                sample_size=len(rows),
                warnings=("peak-to-average is undefined because the average is zero",),
            )
        return StatisticalResult(
            method_id=self.method_id,
            version=self.version,
            applicability="APPLICABLE",
            sample_size=len(rows),
            values={
                "column": column,
                "average": average,
                "peak": {"row_id": peak_row_id, "value": peak},
                "ratio": peak / average,
            },
        )


class TrendSlopeMethod:
    method_id = "trend_slope"
    version = "v1"

    def compute(
        self, dataset: TabularDataset, params: Mapping[str, JsonValue]
    ) -> StatisticalResult:
        column = str(params.get("column", "record_count"))
        time_column = str(params.get("time_column", ""))
        points = sorted(
            (str(time_value), row.row_id, float(value))
            for row in dataset.rows
            if (time_value := row.values.get(time_column)) is not None
            and isinstance((value := row.values.get(column)), int | float)
            and not isinstance(value, bool)
        )
        if len(points) < 2:
            return StatisticalResult(
                method_id=self.method_id,
                version=self.version,
                applicability="NOT_APPLICABLE",
                sample_size=len(points),
                warnings=("trend slope requires at least two ordered points",),
            )
        x_mean = (len(points) - 1) / 2
        y_mean = statistics.fmean(item[2] for item in points)
        denominator = sum((index - x_mean) ** 2 for index in range(len(points)))
        slope = (
            sum((index - x_mean) * (item[2] - y_mean) for index, item in enumerate(points))
            / denominator
        )
        return StatisticalResult(
            method_id=self.method_id,
            version=self.version,
            applicability="APPLICABLE",
            sample_size=len(points),
            values={"column": column, "time_column": time_column, "slope_per_period": slope},
        )


class MadRobustZScoreMethod:
    method_id = "mad_robust_zscore"
    version = "v1"
    minimum_rows = 14

    def compute(
        self, dataset: TabularDataset, params: Mapping[str, JsonValue]
    ) -> StatisticalResult:
        column = str(params.get("column", "record_count"))
        raw_threshold = params.get("threshold", 3.5)
        threshold = float(raw_threshold) if isinstance(raw_threshold, int | float | str) else 3.5
        rows = _numeric_rows(dataset, column)
        if len(rows) < self.minimum_rows:
            return StatisticalResult(
                method_id=self.method_id,
                version=self.version,
                applicability="NOT_APPLICABLE",
                sample_size=len(rows),
                warnings=(f"MAD requires at least {self.minimum_rows} rows",),
            )
        median = statistics.median(value for _, value in rows)
        mad = statistics.median(abs(value - median) for _, value in rows)
        if mad == 0:
            return StatisticalResult(
                method_id=self.method_id,
                version=self.version,
                applicability="NOT_APPLICABLE",
                sample_size=len(rows),
                warnings=("MAD is zero; anomaly screening is not applicable",),
            )
        scores = [(row_id, round(0.6745 * (value - median) / mad, 6)) for row_id, value in rows]
        return StatisticalResult(
            method_id=self.method_id,
            version=self.version,
            applicability="APPLICABLE",
            sample_size=len(rows),
            values={
                "column": column,
                "median": median,
                "mad": mad,
                "threshold": threshold,
                "screened_anomalies": [
                    {"row_id": row_id, "robust_z": score}
                    for row_id, score in scores
                    if abs(score) > threshold
                ],
            },
            warnings=("anomalies are exploratory screening, not fault conclusions",),
        )


class PeriodChangeMethod:
    method_id = "period_change"
    version = "v1"

    def compute(
        self, dataset: TabularDataset, params: Mapping[str, JsonValue]
    ) -> StatisticalResult:
        time_column = str(params.get("time_column", ""))
        value_column = str(params.get("column", "record_count"))
        points = sorted(
            (
                (str(time_value), row.row_id, float(value))
                for row in dataset.rows
                if (time_value := row.values.get(time_column)) is not None
                and isinstance((value := row.values.get(value_column)), int | float)
                and not isinstance(value, bool)
            ),
            key=lambda item: (item[0], item[1]),
        )
        if len(points) < 2:
            return StatisticalResult(
                method_id=self.method_id,
                version=self.version,
                applicability="NOT_APPLICABLE",
                sample_size=len(points),
                warnings=("period comparison requires at least two ordered points",),
            )
        first_time, first_row_id, first_value = points[0]
        last_time, last_row_id, last_value = points[-1]
        change = last_value - first_value
        change_rate = None if first_value == 0 else round(change / first_value, 6)
        peak_time, peak_row_id, peak_value = max(points, key=lambda item: (item[2], item[0]))
        return StatisticalResult(
            method_id=self.method_id,
            version=self.version,
            applicability="APPLICABLE",
            sample_size=len(points),
            values={
                "column": value_column,
                "time_column": time_column,
                "first": {
                    "time": first_time,
                    "row_id": first_row_id,
                    "value": first_value,
                },
                "last": {
                    "time": last_time,
                    "row_id": last_row_id,
                    "value": last_value,
                },
                "absolute_change": change,
                "change_rate": change_rate,
                "peak": {"time": peak_time, "row_id": peak_row_id, "value": peak_value},
            },
        )


class StatisticEngine:
    def __init__(self) -> None:
        methods: tuple[StatisticalMethod, ...] = (
            RankMethod(),
            ContributionMethod(),
            WithinGroupContributionMethod(),
            MeanMedianMethod(),
            PercentileMethod(),
            StdCvMethod(),
            MovingAverageMethod(),
            MadRobustZScoreMethod(),
            HhiMethod(),
            ParetoMethod(),
            PeakToAverageMethod(),
            TrendSlopeMethod(),
            PeriodChangeMethod(),
        )
        self.methods = {item.method_id: item for item in methods}

    def compute(
        self,
        method_id: str,
        dataset: TabularDataset,
        params: Mapping[str, JsonValue],
    ) -> StatisticalResult:
        method = self.methods.get(method_id)
        if method is None:
            return StatisticalResult(
                method_id=method_id,
                version="unknown",
                applicability="NOT_APPLICABLE",
                sample_size=len(dataset.rows),
                warnings=("statistical method is not registered",),
            )
        return method.compute(dataset, params)
