"""Deterministic Semantic Package serialization and integrity verification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from app.contracts.common import semantic_hash
from app.contracts.dashboard import VisualizationDefinition
from app.contracts.metric import (
    AnalysisRecipe,
    MeasureDefinition,
    MethodDefinition,
    MetricDefinition,
    ValueDictionary,
)
from app.contracts.semantic import (
    CanonicalField,
    DatasetDefinition,
    EntityDefinition,
    ImportReport,
    PolicyDefinition,
    SemanticManifest,
)


class SemanticPackageError(ValueError):
    pass


def write_json(path: Path, value: Any) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    elif isinstance(value, (tuple, list)):
        value = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in value
        ]
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SemanticPackageError(f"cannot read semantic package file {path}: {error}") from error


class CompiledSemanticPackage:
    def __init__(self, package_dir: Path) -> None:
        self.package_dir = package_dir.resolve()
        self.manifest = SemanticManifest.model_validate_json(
            (self.package_dir / "manifest.json").read_text(encoding="utf-8")
        )
        self._verify_hashes()

    def fields(self) -> tuple[CanonicalField, ...]:
        raw = (self.package_dir / "fields.json").read_text(encoding="utf-8")
        return tuple(TypeAdapter(list[CanonicalField]).validate_json(raw))

    def import_report(self) -> ImportReport:
        return ImportReport.model_validate_json(
            (self.package_dir / "import_report.json").read_text(encoding="utf-8")
        )

    def datasets(self) -> tuple[DatasetDefinition, ...]:
        raw = (self.package_dir / "datasets.json").read_text(encoding="utf-8")
        return tuple(TypeAdapter(list[DatasetDefinition]).validate_json(raw))

    def metrics(self) -> tuple[MetricDefinition, ...]:
        raw = (self.package_dir / "metrics.json").read_text(encoding="utf-8")
        return tuple(TypeAdapter(list[MetricDefinition]).validate_json(raw))

    def measures(self) -> tuple[MeasureDefinition, ...]:
        path = self.package_dir / "measures.json"
        if not path.exists():
            return ()
        return tuple(TypeAdapter(list[MeasureDefinition]).validate_json(path.read_text("utf-8")))

    def entities(self) -> tuple[EntityDefinition, ...]:
        path = self.package_dir / "entities.json"
        if not path.exists():
            return ()
        return tuple(TypeAdapter(list[EntityDefinition]).validate_json(path.read_text("utf-8")))

    def values(self) -> tuple[ValueDictionary, ...]:
        raw = (self.package_dir / "values.json").read_text(encoding="utf-8")
        return tuple(TypeAdapter(list[ValueDictionary]).validate_json(raw))

    def methods(self) -> tuple[MethodDefinition, ...]:
        raw = (self.package_dir / "methods.json").read_text(encoding="utf-8")
        return tuple(TypeAdapter(list[MethodDefinition]).validate_json(raw))

    def recipes(self) -> tuple[AnalysisRecipe, ...]:
        raw = (self.package_dir / "recipes.json").read_text(encoding="utf-8")
        return tuple(TypeAdapter(list[AnalysisRecipe]).validate_json(raw))

    def visualizations(self) -> tuple[VisualizationDefinition, ...]:
        raw = (self.package_dir / "visualizations.json").read_text(encoding="utf-8")
        return tuple(TypeAdapter(list[VisualizationDefinition]).validate_json(raw))

    def policies(self) -> tuple[PolicyDefinition, ...]:
        raw = (self.package_dir / "policies.json").read_text(encoding="utf-8")
        return tuple(TypeAdapter(list[PolicyDefinition]).validate_json(raw))

    def read_payload(self, name: str) -> Any:
        if name not in self.manifest.file_hashes:
            raise SemanticPackageError(f"file is not declared in manifest: {name}")
        if name.endswith(".jsonl"):
            return [
                json.loads(line)
                for line in (self.package_dir / name).read_text(encoding="utf-8").splitlines()
                if line
            ]
        return read_json(self.package_dir / name)

    def _verify_hashes(self) -> None:
        for name, expected_hash in self.manifest.file_hashes.items():
            path = (self.package_dir / name).resolve()
            if self.package_dir not in path.parents:
                raise SemanticPackageError(f"manifest path escapes package: {name}")
            actual_hash = semantic_hash(
                [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
                if name.endswith(".jsonl")
                else read_json(path)
            )
            if actual_hash != expected_hash:
                raise SemanticPackageError(
                    f"semantic package hash mismatch for {name}: {actual_hash} != {expected_hash}"
                )
