"""Minimize structured payloads before they reach an LLM adapter."""

from typing import Any

SECRET_KEYS = frozenset({"password", "secret", "token", "api_key", "authorization", "credential"})


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in SECRET_KEYS else redact_secrets(child)
            for key, child in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact_secrets(item) for item in value]
    return value
