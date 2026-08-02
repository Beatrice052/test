"""Blocking Excel, Mapping, and Metric conflict cases."""

from pathlib import Path

import pytest

from app.contracts.semantic import ImportReport
from app.semantic.compiler import (
    SemanticCompileError,
    SemanticCompileExit,
    compile_semantic_package,
)

ROOT = Path(__file__).resolve().parents[4]
INPUT = ROOT / "semantic-input" / "mock"


def _read_failed_report(output_dir: Path) -> ImportReport:
    return ImportReport.model_validate_json(
        (output_dir / "import_report.json").read_text(encoding="utf-8")
    )


def test_duplicate_excel_field_with_different_definition_blocks_compile(tmp_path: Path) -> None:
    catalog_path = tmp_path / "duplicate.csv"
    catalog_path.write_text(
        "field_path,description\nchannel,渠道定义A\nchannel,渠道定义B\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"

    with pytest.raises(SemanticCompileError) as error:
        compile_semantic_package(INPUT, output_dir, field_catalog_path=catalog_path)

    assert error.value.exit_code == SemanticCompileExit.INVALID_INPUT
    report = _read_failed_report(output_dir)
    assert report.status == "FAILED"
    assert report.duplicate_field_paths == ("channel",)
    assert any(issue.code == "DUPLICATE_FIELD_PATH" for issue in report.issues)


def test_incompatible_monthly_mapping_blocks_compile(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"

    with pytest.raises(SemanticCompileError) as error:
        compile_semantic_package(
            INPUT,
            output_dir,
            mapping_path=ROOT / "fixtures" / "opensearch" / "mapping_conflict.json",
        )

    assert error.value.exit_code == SemanticCompileExit.MAPPING_CONFLICT
    report = _read_failed_report(output_dir)
    assert "sub_message.channel" in report.type_conflicts


def test_ambiguous_excel_leaf_name_is_not_guessed(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"

    with pytest.raises(SemanticCompileError) as error:
        compile_semantic_package(
            INPUT,
            output_dir,
            mapping_path=ROOT / "fixtures" / "opensearch" / "mapping_ambiguous.json",
        )

    assert error.value.exit_code == SemanticCompileExit.AMBIGUOUS_FIELD
    report = _read_failed_report(output_dir)
    assert 4 in report.ambiguous_rows


def test_invalid_failure_rate_status_group_blocks_compile(tmp_path: Path) -> None:
    metric_dir = tmp_path / "metric_registry"
    metric_dir.mkdir()
    metric_path = metric_dir / "failure_rate.v1.yaml"
    metric_text = (
        (INPUT / "metric_registry" / "failure_rate.v1.yaml")
        .read_text(encoding="utf-8")
        .replace("status_group: failure", "status_group: impossible_group")
    )
    metric_path.write_text(metric_text, encoding="utf-8")
    output_dir = tmp_path / "output"

    with pytest.raises(SemanticCompileError) as error:
        compile_semantic_package(INPUT, output_dir, metric_registry_path=metric_dir)

    assert error.value.exit_code == SemanticCompileExit.INVALID_METRIC
    report = _read_failed_report(output_dir)
    assert report.invalid_metric_bindings == ("failure_rate.v1",)
