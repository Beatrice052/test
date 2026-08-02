"""Generate checked-in OpenAPI JSON and TypeScript schema types without Node codegen."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
OUTPUT = ROOT / "frontend" / "src" / "api"
sys.path.insert(0, str(BACKEND))

from app.main import create_app


def join_unique(items: list[str], operator: str) -> str:
    return operator.join(dict.fromkeys(items))


def ts_type(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return str(schema["$ref"]).rsplit("/", 1)[-1]
    if "const" in schema:
        return json.dumps(schema["const"], ensure_ascii=False)
    if "enum" in schema:
        return " | ".join(
            json.dumps(item, ensure_ascii=False) for item in schema["enum"]
        )
    if "anyOf" in schema:
        return join_unique([ts_type(item) for item in schema["anyOf"]], " | ")
    if "oneOf" in schema:
        return join_unique([ts_type(item) for item in schema["oneOf"]], " | ")
    if "allOf" in schema:
        return join_unique([ts_type(item) for item in schema["allOf"]], " & ")
    kind = schema.get("type")
    if isinstance(kind, list):
        return join_unique([ts_type({**schema, "type": item}) for item in kind], " | ")
    if kind == "string":
        return "string"
    if kind in {"integer", "number"}:
        return "number"
    if kind == "boolean":
        return "boolean"
    if kind == "null":
        return "null"
    if kind == "array":
        return f"Array<{ts_type(schema.get('items', {}))}>"
    if kind == "object" or "properties" in schema:
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        lines = []
        for name, value in properties.items():
            safe_name = (
                name
                if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", name)
                else json.dumps(name)
            )
            optional = "" if name in required else "?"
            lines.append(f"  {safe_name}{optional}: {ts_type(value)};")
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            lines.append(f"  [key: string]: {ts_type(additional)};")
        if not lines:
            return "Record<string, unknown>"
        return "{\n" + "\n".join(lines) + "\n}"
    if isinstance(schema.get("additionalProperties"), dict):
        return f"Record<string, {ts_type(schema['additionalProperties'])}>"
    return "unknown"


def render_outputs() -> tuple[str, str, int]:
    openapi = create_app().openapi()
    schemas = openapi.get("components", {}).get("schemas", {})
    openapi_text = (
        json.dumps(openapi, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    lines = [
        "/* Generated from backend OpenAPI by scripts/generate_frontend_types.py. */",
        "/* Do not edit manually. */",
        "",
    ]
    for name in sorted(schemas):
        lines.append(f"export type {name} = {ts_type(schemas[name])};")
        lines.append("")
    return openapi_text, "\n".join(lines), len(schemas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    openapi_text, generated_text, schema_count = render_outputs()
    expected = {
        OUTPUT / "openapi.json": openapi_text,
        OUTPUT / "generated.ts": generated_text,
    }
    if args.check:
        drifted = [
            path
            for path, content in expected.items()
            if not path.exists() or path.read_text(encoding="utf-8") != content
        ]
        if drifted:
            print("generated API artifacts are stale: " + ", ".join(map(str, drifted)))
            return 1
        print(f"verified {schema_count} TypeScript schemas and OpenAPI JSON")
        return 0
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for path, content in expected.items():
        path.write_text(content, encoding="utf-8", newline="\n")
    print(f"generated {schema_count} TypeScript schemas and OpenAPI JSON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
