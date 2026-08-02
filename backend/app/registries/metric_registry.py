"""Metric registry with YAML-to-formula AST normalization."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, cast

from app.contracts.metric import FormulaNode, MetricDefinition, MetricLevel
from app.registries.base import RegistryLoadError, iter_yaml_files, load_yaml, normalize_items

LEVEL_ALIASES = {
    "certified": MetricLevel.CERTIFIED,
    "governed_derived": MetricLevel.GOVERNED_DERIVED,
    "exploratory": MetricLevel.EXPLORATORY,
    "unsupported": MetricLevel.UNSUPPORTED,
}
type FormulaOperator = Literal[
    "constant",
    "column",
    "filtered_count",
    "add",
    "subtract",
    "multiply",
    "divide",
    "sum",
]
FORMULA_OPERATORS: set[str] = {
    "constant",
    "column",
    "filtered_count",
    "add",
    "subtract",
    "multiply",
    "divide",
    "sum",
}


def _formula_node(raw: Any) -> FormulaNode:
    if not isinstance(raw, Mapping):
        raise RegistryLoadError("formula node must be an object")
    operator = str(raw.get("operator") or raw.get("type") or "")
    if operator not in FORMULA_OPERATORS:
        raise RegistryLoadError(f"unsupported formula operator: {operator}")
    status_groups_raw = raw.get("status_groups")
    if status_groups_raw is None and raw.get("status_group") is not None:
        status_groups_raw = [raw["status_group"]]
    operands_raw = raw.get("operands", ())
    return FormulaNode(
        operator=cast(FormulaOperator, operator),
        value=raw.get("value"),
        column=raw.get("column"),
        status_groups=tuple(str(item) for item in (status_groups_raw or ())),
        operands=tuple(_formula_node(item) for item in operands_raw),
    )


def _normalize_metric(raw: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(raw)
    level = normalized.get("level")
    if isinstance(level, str):
        normalized["level"] = LEVEL_ALIASES.get(level.lower(), level.upper())
    if normalized.get("numerator") is not None:
        normalized["numerator"] = _formula_node(normalized["numerator"])
    if normalized.get("denominator") is not None:
        normalized["denominator"] = _formula_node(normalized["denominator"])
    if normalized.get("formula") is not None:
        normalized["formula"] = _formula_node(normalized["formula"])
    dimensions = normalized.get("dimensions", ())
    normalized["dimensions"] = tuple(str(item) for item in dimensions)
    if normalized.get("time_semantics") is None:
        normalized.pop("time_semantics", None)
    normalized.pop("formula_engine", None)
    normalized.pop("tests", None)
    return normalized


class MetricRegistry:
    def __init__(self, definitions: tuple[MetricDefinition, ...]) -> None:
        self.definitions = definitions
        self.by_versioned_id: dict[str, MetricDefinition] = {}
        for definition in definitions:
            if definition.versioned_id in self.by_versioned_id:
                raise RegistryLoadError(f"duplicate metric: {definition.versioned_id}")
            self.by_versioned_id[definition.versioned_id] = definition

    @classmethod
    def load(cls, path: Path) -> "MetricRegistry":
        definitions: list[MetricDefinition] = []
        for file_path in iter_yaml_files(path):
            for item in normalize_items(load_yaml(file_path), container_key="metrics"):
                definitions.append(
                    MetricDefinition.model_validate(_normalize_metric(item), strict=False)
                )
        return cls(tuple(definitions))
