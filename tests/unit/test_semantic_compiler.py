from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest

from app.semantic.compiler import (
    SemanticCompilationError,
    SemanticCompiler,
    SemanticSourcePaths,
)
from app.semantic.models import FieldAccess, SemanticMaturity

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _paths(root: Path = PROJECT_ROOT) -> SemanticSourcePaths:
    return SemanticSourcePaths.from_project_root(root)


def _copy_sources(tmp_path: Path) -> SemanticSourcePaths:
    target = tmp_path / "semantic_sources"
    shutil.copytree(PROJECT_ROOT / "semantic_sources", target)
    return SemanticSourcePaths.from_project_root(tmp_path)


def test_semantic_compiler_aligns_mapping_catalog_metrics_and_policy() -> None:
    result = SemanticCompiler(_paths()).compile()
    fields = result.model.field_map()
    metrics = result.model.metric_map()

    assert result.report.status == "PASSED_WITH_WARNINGS"
    assert result.report.catalog_only_fields == ["catalogOnlyField"]
    assert "mappingOnlyFlag" in result.report.mapping_only_fields
    assert "deliveryMeta.attemptId" in result.report.mapping_only_fields
    assert fields["subjectText"].physical_aggregation_path == "subjectText.keyword"
    assert fields["subjectText"].aggregatable is True
    assert fields["diagnosticText"].aggregatable is False
    assert fields["mappingOnlyFlag"].semantic_maturity == SemanticMaturity.MAPPING_ONLY
    assert fields["mappingOnlyFlag"].access == FieldAccess.ALLOWED
    assert fields["messageBody"].access == FieldAccess.BLOCKED
    assert fields["createdTime"].mapping_type == "date"
    assert metrics["failure_rate"].lifecycle_field == "status"
    assert metrics["failure_rate"].version == "failure_rate.v1"
    assert result.model.dataset.index_pattern == "tbl_os_sub_message_{yyyy}_{mm}"


def test_candidate_role_is_removed_before_hash_and_model(tmp_path: Path) -> None:
    paths = _copy_sources(tmp_path)
    original = SemanticCompiler(paths).compile()
    with paths.catalog.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0])
    for index, row in enumerate(rows):
        row["candidate_role"] = f"untrusted-random-value-{index}"
    with paths.catalog.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    mutated = SemanticCompiler(paths).compile()

    assert mutated.model == original.model
    assert mutated.model.catalog_hash == original.model.catalog_hash
    assert "candidate_role" not in mutated.model.model_dump_json()
    assert mutated.report.ignored_columns == ["candidate_role"]


def test_mapping_type_is_authoritative_over_catalog(tmp_path: Path) -> None:
    paths = _copy_sources(tmp_path)
    rows = paths.catalog.read_text(encoding="utf-8").splitlines()
    rows = [
        row.replace("createdTime,date,", "createdTime,keyword,")
        if row.startswith("createdTime,")
        else row
        for row in rows
    ]
    paths.catalog.write_text("\n".join(rows) + "\n", encoding="utf-8")

    result = SemanticCompiler(paths).compile()

    assert result.model.field_map()["createdTime"].mapping_type == "date"
    assert result.report.type_conflicts == [
        {
            "field_path": "createdTime",
            "catalog_type": "keyword",
            "mapping_type": "date",
        }
    ]


def test_duplicate_field_path_fails_compilation(tmp_path: Path) -> None:
    paths = _copy_sources(tmp_path)
    lines = paths.catalog.read_text(encoding="utf-8").splitlines()
    paths.catalog.write_text("\n".join([*lines, lines[1]]) + "\n", encoding="utf-8")

    with pytest.raises(SemanticCompilationError, match="duplicate field_path"):
        SemanticCompiler(paths).compile()


def test_compile_to_directory_writes_reviewable_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "runtime"

    result = SemanticCompiler(_paths()).compile_to_directory(output)

    assert (output / "compiled_semantic_model.json").exists()
    assert (output / "semantic_import_report.json").exists()
    assert result.model.model_version in (output / "compiled_semantic_model.json").read_text(
        encoding="utf-8"
    )
