"""Metric Registry and formula AST validation."""

from pathlib import Path

import pytest

from app.registries.base import RegistryLoadError
from app.registries.metric_registry import MetricRegistry, _formula_node

ROOT = Path(__file__).resolve().parents[4]


def test_failure_rate_registry_preserves_formula_version_and_denominator() -> None:
    registry = MetricRegistry.load(ROOT / "semantic-input" / "mock" / "metric_registry")
    failure_rate = registry.by_versioned_id["failure_rate.v1"]

    assert failure_rate.numerator is not None
    assert failure_rate.numerator.status_groups == ("failure",)
    assert failure_rate.denominator is not None
    assert failure_rate.denominator.status_groups == ("success", "failure")
    assert failure_rate.minimum_denominator == 30


def test_formula_registry_rejects_unknown_operator() -> None:
    with pytest.raises(RegistryLoadError, match="unsupported formula operator"):
        _formula_node({"operator": "python_eval", "value": "danger"})
