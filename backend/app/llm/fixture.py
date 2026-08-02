"""Exact structured responses for Golden tests and deterministic CI."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from app.llm.client import ALLOWED_OPERATIONS, OutputModel


class FixtureNotFoundError(LookupError):
    pass


class FixtureLLMClient:
    """Return pre-reviewed JSON by operation and fixture_id; never executes model code."""

    def __init__(self, responses: dict[str, dict[str, Any]]) -> None:
        self._responses = copy.deepcopy(responses)
        self.calls: list[tuple[str, str]] = []

    @classmethod
    def from_file(cls, path: Path) -> FixtureLLMClient:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("LLM fixture root must be an object")
        responses: dict[str, dict[str, Any]] = {}
        for operation, fixtures in raw.items():
            if operation not in ALLOWED_OPERATIONS or not isinstance(fixtures, dict):
                raise ValueError(f"invalid LLM fixture operation: {operation}")
            responses[str(operation)] = {str(key): value for key, value in fixtures.items()}
        return cls(responses)

    async def generate(
        self,
        *,
        operation: str,
        system_prompt: str,
        input_payload: dict[str, object],
        output_schema: type[OutputModel],
        timeout_seconds: float,
        correlation_id: str,
    ) -> OutputModel:
        del system_prompt, timeout_seconds
        if operation not in ALLOWED_OPERATIONS:
            raise ValueError(f"operation is not allowed: {operation}")
        fixture_id = str(input_payload.get("fixture_id", "default"))
        try:
            payload = self._responses[operation][fixture_id]
        except KeyError as error:
            raise FixtureNotFoundError(f"missing fixture: {operation}/{fixture_id}") from error
        resolved_payload = self._interpolate(copy.deepcopy(payload), input_payload)
        self.calls.append((operation, correlation_id))
        return output_schema.model_validate_json(
            json.dumps(resolved_payload, ensure_ascii=False), strict=True
        )

    @classmethod
    def _interpolate(cls, value: Any, input_payload: dict[str, object]) -> Any:
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            resolved: Any = input_payload
            for part in value[2:-1].split("."):
                if isinstance(resolved, dict) and part in resolved:
                    resolved = resolved[part]
                elif isinstance(resolved, list) and part.isdigit() and int(part) < len(resolved):
                    resolved = resolved[int(part)]
                else:
                    raise FixtureNotFoundError(f"fixture interpolation path is missing: {value}")
            return copy.deepcopy(resolved)
        if isinstance(value, dict):
            return {key: cls._interpolate(child, input_payload) for key, child in value.items()}
        if isinstance(value, list):
            return [cls._interpolate(child, input_payload) for child in value]
        return value
