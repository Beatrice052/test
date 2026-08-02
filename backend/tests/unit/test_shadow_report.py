"""Shadow report stores hashes and verdicts, never copied business payloads."""

import json
import runpy
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _builder() -> Any:
    return cast(
        Any,
        runpy.run_path(str(ROOT / "scripts" / "build_shadow_report.py"))["build_report"],
    )


def test_report_requires_all_layers_and_does_not_embed_payloads(tmp_path: Path) -> None:
    paths: dict[str, Path] = {}
    for name in (
        "analysis_plan",
        "query_plan",
        "compiled_dsl",
        "normalized_dataset",
        "dashboard_evidence",
    ):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps({"layer": name, "secret_value": "not-in-report"}))
        paths[name] = path
    metric = tmp_path / "metric_result.json"
    metric.write_text(json.dumps({"value": 0.2, "numerator": 2, "denominator": 10}))
    paths["metric_result"] = metric

    report = _builder()(
        case_id="G04-internal",
        artifacts=paths,
        old_result=None,
        classification="DATA_CHANGE",
        business_verdict="NEEDS_REVIEW",
        require_ratio_evidence=True,
    )

    serialized = json.dumps(report)
    assert report["required_artifacts_complete"] is True
    assert report["ratio_evidence_complete"] is True
    assert "not-in-report" not in serialized
    assert report["payloads_embedded"] is False


def test_ratio_case_refuses_missing_numerator_denominator(tmp_path: Path) -> None:
    paths = {}
    for name in (
        "analysis_plan",
        "query_plan",
        "compiled_dsl",
        "normalized_dataset",
        "metric_result",
        "dashboard_evidence",
    ):
        path = tmp_path / f"{name}.json"
        path.write_text("{}")
        paths[name] = path
    with pytest.raises(ValueError, match="numerator and denominator"):
        _builder()(
            case_id="G04-internal",
            artifacts=paths,
            old_result=None,
            classification="UNKNOWN_NEEDS_INVESTIGATION",
            business_verdict="NEEDS_REVIEW",
            require_ratio_evidence=True,
        )
