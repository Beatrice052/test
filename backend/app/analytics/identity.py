"""Stable logical row identity independent of measure values."""

import hashlib
from collections.abc import Mapping, Sequence

from app.contracts.common import JsonValue, canonical_json

NULL_SENTINEL = "__NULL__"


def stable_row_id(
    dataset_id: str,
    grain: Sequence[str],
    values: Mapping[str, JsonValue],
) -> str:
    key = {field: values.get(field, NULL_SENTINEL) for field in grain}
    canonical = canonical_json({"dataset_id": dataset_id, "grain": grain, "key": key})
    return f"row_{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"
