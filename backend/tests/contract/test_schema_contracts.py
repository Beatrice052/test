"""Positive and negative validation for every authoritative schema model."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.contracts import SCHEMA_MODELS


def _resolve(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in schema:
        return root["$defs"][schema["$ref"].rsplit("/", 1)[-1]]
    if "anyOf" in schema:
        option = next(candidate for candidate in schema["anyOf"] if candidate.get("type") != "null")
        return _resolve(option, root)
    return schema


def _string_value(name: str, schema: dict[str, Any]) -> str:
    if "enum" in schema:
        return str(schema["enum"][0])
    if schema.get("format") == "date-time":
        return "2026-07-31T00:00:00Z"
    pattern = schema.get("pattern", "")
    if "sha256" in pattern:
        return "sha256:" + "0" * 64
    if name == "row_id":
        return "row_" + "0" * 16
    if name == "session_id":
        return "ses_contract"
    if name == "code" and "REQ" in pattern:
        return "REQ_INVALID"
    if name in {"schema_version"}:
        return "1.0"
    if name in {"version", "metric_version"}:
        return "v1"
    if name.endswith("_at") or name in {"from_inclusive", "to_exclusive"}:
        return "2026-07-31T00:00:00Z"
    if name == "object_id":
        return "obj_contract"
    if name == "item_id":
        return "item.contract"
    if name.endswith("_id") or name in {"producer", "query"}:
        return "contract_item"
    return "value"


def _minimal(schema: dict[str, Any], root: dict[str, Any], *, name: str = "value") -> Any:
    schema = _resolve(schema, root)
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    schema_type = schema.get("type")
    if schema_type == "object" or "properties" in schema:
        result = {
            key: _minimal(schema["properties"][key], root, name=key)
            for key in schema.get("required", ())
        }
        title = schema.get("title")
        if title == "TimeRange":
            result["from_inclusive"] = "2026-07-01T00:00:00+08:00"
            result["to_exclusive"] = "2026-08-01T00:00:00+08:00"
            result["timezone"] = "Asia/Hong_Kong"
        elif title == "FormulaNode":
            result["operator"] = "constant"
            result["value"] = 1.0
        elif title == "MetricDefinition":
            result["formula"] = {"operator": "constant", "value": 1.0}
        return result
    if schema_type == "array":
        minimum = int(schema.get("minItems", 0))
        return [_minimal(schema.get("items", {}), root) for _ in range(minimum)]
    if schema_type == "integer":
        return int(schema.get("minimum", 0))
    if schema_type == "number":
        return float(schema.get("minimum", 0))
    if schema_type == "boolean":
        return False
    if schema_type == "null":
        return None
    return _string_value(name, schema)


@pytest.mark.parametrize("model", SCHEMA_MODELS, ids=lambda model: model.__name__)
def test_authoritative_contract_accepts_minimal_json_and_forbids_extra(model: type) -> None:
    schema = model.model_json_schema(mode="validation")
    payload = _minimal(schema, schema)
    validated = model.model_validate_json(json.dumps(payload))
    assert type(validated) is model

    payload["unexpected_field"] = "must fail"
    with pytest.raises(ValidationError) as error:
        model.model_validate_json(json.dumps(payload))
    assert "extra_forbidden" in str(error.value)


@pytest.mark.parametrize("model", SCHEMA_MODELS, ids=lambda model: model.__name__)
def test_authoritative_contract_configuration_is_strict_frozen_closed(model: type) -> None:
    assert model.model_config.get("extra") == "forbid"
    assert model.model_config.get("strict") is True
    assert model.model_config.get("frozen") is True
    schema = model.model_json_schema()
    assert _resolve(schema, schema).get("additionalProperties") is False
