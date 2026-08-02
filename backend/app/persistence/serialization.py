"""Canonical JSON and timezone helpers for SQLite records."""

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel


def utc_now() -> datetime:
    return datetime.now(UTC)


def dump_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_json(value: str) -> Any:
    return json.loads(value)


def dump_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def load_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
