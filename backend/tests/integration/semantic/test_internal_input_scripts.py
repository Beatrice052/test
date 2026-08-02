"""Internal handoff scripts require only real inputs and business decisions."""

from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any, cast

from app.semantic.compiler import SemanticCompileExit, compile_semantic_package

ROOT = Path(__file__).resolve().parents[4]
MOCK = ROOT / "semantic-input" / "mock"


def _function(script: str, name: str) -> Any:
    module = runpy.run_path(str(ROOT / "scripts" / script))
    return cast(Any, module[name])


def test_prepare_candidate_compiles_without_unconfirmed_failure_rate(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    prepare = _function("prepare_internal_input.py", "prepare")
    indices = prepare(
        field_catalog=MOCK / "field_descriptions.csv",
        mapping=MOCK / "mapping_snapshot.json",
        output_dir=candidate,
    )

    result = compile_semantic_package(candidate, tmp_path / "compiled-record-count-only")

    assert indices == (
        "tbl_os_sub_message_2026_05",
        "tbl_os_sub_message_2026_06",
        "tbl_os_sub_message_2026_07",
    )
    assert result.exit_code == SemanticCompileExit.PASSED
    assert not (candidate / "metric_registry" / "failure_rate.v1.yaml").exists()


def test_confirmed_status_parameters_enable_failure_rate(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    prepare = _function("prepare_internal_input.py", "prepare")
    configure = _function("configure_failure_rate.py", "configure")
    prepare(
        field_catalog=MOCK / "field_descriptions.csv",
        mapping=MOCK / "mapping_snapshot.json",
        output_dir=candidate,
    )
    configure(
        input_dir=candidate,
        success=("DELIVERED", "SENT"),
        failure=("FAILED", "REJECTED"),
        pending=("PENDING",),
        unknown=("UNKNOWN",),
        null_group="unknown",
        minimum_denominator=30,
        owner="approved_business_owner",
    )

    result = compile_semantic_package(candidate, tmp_path / "compiled-confirmed")

    assert result.exit_code == SemanticCompileExit.PASSED
    assert (candidate / "metric_registry" / "failure_rate.v1.yaml").is_file()
    assert "failure_rate.v1" in (candidate / "recipes" / "channel_overview.v1.yaml").read_text(
        encoding="utf-8"
    )
