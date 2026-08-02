"""Assemble a complete internal candidate input from real catalog and Mapping files."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "semantic-input" / "internal-template"


def _mapping_indices(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, dict):
        raise TypeError("Mapping Snapshot root must be an object")
    indices = raw.get("indices")
    if isinstance(indices, dict | list):
        names = tuple(sorted(str(name) for name in indices))
    else:
        names = tuple(
            sorted(
                str(name)
                for name, body in raw.items()
                if isinstance(body, dict) and "mappings" in body
            )
        )
    if not names or any(not re.fullmatch(r"[A-Za-z0-9_.*-]+", name) for name in names):
        raise ValueError("Mapping Snapshot contains no safe index names")
    return names


def _inferred_pattern(indices: tuple[str, ...]) -> str:
    patterns = {
        re.sub(r"(?<!\d)(?:19|20)\d{2}_(?:0[1-9]|1[0-2])(?!\d)", "{YYYY}_{MM}", index)
        for index in indices
    }
    return next(iter(patterns)) if len(patterns) == 1 else indices[0]


def prepare(
    *,
    field_catalog: Path,
    mapping: Path,
    output_dir: Path,
    index_pattern: str | None = None,
) -> tuple[str, ...]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("output directory must be new or empty")
    if field_catalog.suffix.lower() not in {".xlsx", ".csv"}:
        raise ValueError("field catalog must be .xlsx or .csv")
    raw_mapping = json.loads(mapping.read_text(encoding="utf-8"))
    indices = _mapping_indices(raw_mapping)
    output_dir.mkdir(parents=True, exist_ok=True)
    for source in TEMPLATE.rglob("*"):
        relative = source.relative_to(TEMPLATE)
        target = output_dir / relative
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    shutil.copy2(
        field_catalog, output_dir / f"field_descriptions{field_catalog.suffix.lower()}"
    )
    shutil.copy2(mapping, output_dir / "mapping_snapshot.json")

    dataset_path = output_dir / "dataset_registry.yaml"
    dataset = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    dataset["datasets"][0]["index_pattern"] = index_pattern or _inferred_pattern(
        indices
    )
    dataset_path.write_text(
        yaml.safe_dump(dataset, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    policy_path = output_dir / "policy.yaml"
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    policy["policies"][0]["allowed_index_patterns"] = list(indices)
    policy_path.write_text(
        yaml.safe_dump(policy, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return indices


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--field-catalog", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--index-pattern")
    args = parser.parse_args()
    indices = prepare(
        field_catalog=args.field_catalog,
        mapping=args.mapping,
        output_dir=args.output_dir,
        index_pattern=args.index_pattern,
    )
    print(
        json.dumps(
            {
                "status": "PASSED",
                "output_dir": str(args.output_dir),
                "indices": list(indices),
                "failure_rate_enabled": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
