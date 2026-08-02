"""Common strict model primitives and canonical hashing."""

import hashlib
import json
import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[Any] | dict[str, Any]
Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_.-]{0,127}$")]
Sha256 = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
ObjectId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{2,127}$")]


class StrictModel(BaseModel):
    """Base for every contract: immutable, strict, and closed to unknown fields."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Provenance(StrictModel):
    """Traceable origin without credentials or large raw payloads."""

    producer: Identifier
    source_ids: tuple[str, ...] = ()
    source_hashes: dict[str, Sha256] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class VersionedModel(StrictModel):
    """Base for persisted and cross-layer authoritative objects."""

    schema_version: str = Field(default="1.0", pattern=r"^[1-9][0-9]*\.[0-9]+$")
    object_id: ObjectId
    created_at: datetime
    content_hash: Sha256
    provenance: Provenance

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class TimeRange(StrictModel):
    """Half-open business time range."""

    from_inclusive: datetime
    to_exclusive: datetime
    timezone: str = Field(min_length=1, max_length=64)

    @field_validator("from_inclusive", "to_exclusive")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("time range values must be timezone-aware")
        return value

    def model_post_init(self, __context: Any) -> None:
        if self.from_inclusive >= self.to_exclusive:
            raise ValueError("time range must satisfy from_inclusive < to_exclusive")


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


def canonical_json(value: Any) -> str:
    """Serialize a value deterministically for identity and snapshots."""

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def semantic_hash(value: Any, *, exclude_keys: frozenset[str] = frozenset()) -> str:
    """Hash normalized JSON while omitting explicitly non-semantic keys."""

    def strip(item: Any) -> Any:
        if isinstance(item, BaseModel):
            item = item.model_dump(mode="json")
        if isinstance(item, dict):
            return {
                key: strip(child) for key, child in sorted(item.items()) if key not in exclude_keys
            }
        if isinstance(item, (list, tuple)):
            return [strip(child) for child in item]
        return item

    digest = hashlib.sha256(canonical_json(strip(value)).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def safe_identifier(value: str) -> str:
    """Normalize an internal semantic name without accepting path syntax."""

    normalized = re.sub(r"[^a-z0-9_.-]+", "_", value.strip().lower()).strip("_.-")
    if not normalized or not re.match(r"^[a-z]", normalized):
        normalized = f"id_{normalized}"
    return normalized[:128]
