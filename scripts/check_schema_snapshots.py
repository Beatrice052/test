#!/usr/bin/env python3
"""Fail when checked-in JSON Schema snapshots differ from code."""

from __future__ import annotations

import difflib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SCHEMA_DIR = ROOT / "docs" / "schemas"

if __name__ == "__main__" and os.environ.get("CHATBI_BACKEND_REEXEC") != "1":
    venv_python = (
        BACKEND / ".venv" / "Scripts" / "python.exe"
        if os.name == "nt"
        else BACKEND / ".venv" / "bin" / "python"
    )
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        environment = {**os.environ, "CHATBI_BACKEND_REEXEC": "1"}
        raise SystemExit(
            subprocess.run(
                [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]],
                env=environment,
                check=False,
            ).returncode
        )

sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_schema_snapshots import render_schema  # noqa: E402

from app.contracts import SCHEMA_MODELS  # noqa: E402


def main() -> int:
    failures: list[str] = []
    expected_names = {f"{model.__name__}.schema.json" for model in SCHEMA_MODELS}
    actual_names = {path.name for path in SCHEMA_DIR.glob("*.schema.json")}
    if expected_names != actual_names:
        failures.append(
            f"schema file set differs: missing={sorted(expected_names - actual_names)}, "
            f"extra={sorted(actual_names - expected_names)}"
        )

    for model in SCHEMA_MODELS:
        path = SCHEMA_DIR / f"{model.__name__}.schema.json"
        if not path.exists():
            continue
        expected = render_schema(model)
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            diff = "".join(
                difflib.unified_diff(
                    actual.splitlines(keepends=True),
                    expected.splitlines(keepends=True),
                    fromfile=str(path),
                    tofile=f"generated:{model.__name__}",
                )
            )
            failures.append(diff)

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"schema snapshots match {len(expected_names)} authoritative models")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
