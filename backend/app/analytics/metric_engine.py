"""Versioned, deterministic Formula AST evaluation for governed metrics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from app.contracts.metric import FormulaNode, MetricDefinition, MetricValue


class MetricEvaluationError(ValueError):
    pass


class FormulaEvaluator:
    def evaluate(
        self,
        node: FormulaNode,
        *,
        columns: Mapping[str, float | int | None],
        status_counts: Mapping[str, int],
    ) -> float | int | None:
        if node.operator == "constant":
            return node.value
        if node.operator == "column":
            return columns.get(node.column or "")
        if node.operator == "filtered_count":
            return sum(status_counts.get(group, 0) for group in node.status_groups)
        operands = [
            self.evaluate(item, columns=columns, status_counts=status_counts)
            for item in node.operands
        ]
        if any(item is None for item in operands):
            return None
        values = [float(item) for item in operands if item is not None]
        if node.operator == "sum":
            return sum(values)
        if len(values) < 2:
            raise MetricEvaluationError(f"{node.operator} requires at least two operands")
        if node.operator == "add":
            return sum(values)
        if node.operator == "subtract":
            return values[0] - sum(values[1:])
        if node.operator == "multiply":
            result = 1.0
            for value in values:
                result *= value
            return result
        if node.operator == "divide":
            result = values[0]
            for value in values[1:]:
                if value == 0:
                    return None
                result /= value
            return result
        raise MetricEvaluationError(f"unsupported formula operator: {node.operator}")


class MetricEngine:
    def __init__(self) -> None:
        self.evaluator = FormulaEvaluator()

    def compute(
        self,
        definition: MetricDefinition,
        *,
        record_count: int,
        status_counts: Mapping[str, int],
        evidence_row_ids: Sequence[str],
    ) -> MetricValue:
        if not definition.enabled:
            raise MetricEvaluationError(f"metric is disabled: {definition.versioned_id}")
        columns: dict[str, int] = {"record_count": record_count}
        excluded = {
            group: count
            for group, count in status_counts.items()
            if group in {"pending", "unknown", "null"} and count > 0
        }
        if definition.numerator is not None and definition.denominator is not None:
            numerator = self.evaluator.evaluate(
                definition.numerator,
                columns=columns,
                status_counts=status_counts,
            )
            denominator = self.evaluator.evaluate(
                definition.denominator,
                columns=columns,
                status_counts=status_counts,
            )
            numerator_value = self._number(numerator)
            denominator_value = self._number(denominator)
            quality: Literal["VALID", "INSUFFICIENT_SAMPLE", "INVALID", "NOT_APPLICABLE"]
            if denominator_value is None or denominator_value == 0:
                value = None
                quality = "INVALID"
            else:
                numerator_for_ratio = numerator_value if numerator_value is not None else 0
                value = round(
                    float(numerator_for_ratio) / float(denominator_value),
                    definition.precision,
                )
                quality = (
                    "INSUFFICIENT_SAMPLE"
                    if denominator_value < definition.minimum_denominator
                    else "VALID"
                )
            return MetricValue(
                metric_id=definition.metric_id,
                metric_version=definition.version,
                value=value,
                unit=definition.unit,
                numerator=numerator_value,
                denominator=denominator_value,
                excluded=excluded,
                quality=quality,
                evidence_row_ids=tuple(evidence_row_ids),
            )
        if definition.formula is None:
            raise MetricEvaluationError("metric has no executable formula")
        value = self.evaluator.evaluate(
            definition.formula,
            columns=columns,
            status_counts=status_counts,
        )
        numeric = self._number(value)
        rounded: float | int | None = (
            round(float(numeric), definition.precision) if numeric is not None else None
        )
        if definition.precision == 0 and rounded is not None:
            rounded = int(rounded)
        return MetricValue(
            metric_id=definition.metric_id,
            metric_version=definition.version,
            value=rounded,
            unit=definition.unit,
            excluded=excluded,
            quality="VALID" if rounded is not None else "INVALID",
            evidence_row_ids=tuple(evidence_row_ids),
        )

    @staticmethod
    def _number(value: float | int | None) -> float | int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise MetricEvaluationError("boolean is not a metric number")
        return value
