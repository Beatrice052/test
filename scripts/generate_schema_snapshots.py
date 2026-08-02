#!/usr/bin/env python3
"""Generate deterministic JSON Schema snapshots for every authoritative model."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SCHEMA_DIR = ROOT / "docs" / "schemas"
sys.path.insert(0, str(BACKEND))

from app.contracts import SCHEMA_MODELS


def render_schema(model: type) -> str:
    schema = model.model_json_schema(mode="validation")
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    expected_names: set[str] = set()
    for model in SCHEMA_MODELS:
        name = f"{model.__name__}.schema.json"
        expected_names.add(name)
        (SCHEMA_DIR / name).write_text(
            render_schema(model), encoding="utf-8", newline="\n"
        )

    for path in SCHEMA_DIR.glob("*.schema.json"):
        if path.name not in expected_names:
            path.unlink()

    print(f"generated {len(expected_names)} schema snapshots in {SCHEMA_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
