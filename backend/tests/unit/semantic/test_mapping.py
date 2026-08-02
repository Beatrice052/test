"""Mapping flatten, multi-field, nested, and cross-month compatibility tests."""

import json
from pathlib import Path

from app.contracts.semantic import MappingCompatibility
from app.semantic.capability import infer_compatibility
from app.semantic.mapping import flatten_mapping_snapshot

ROOT = Path(__file__).resolve().parents[4]


def test_mapping_flattens_keyword_multifield_nested_and_date() -> None:
    raw = json.loads(
        (ROOT / "semantic-input" / "mock" / "mapping_snapshot.json").read_text(encoding="utf-8")
    )
    snapshot = flatten_mapping_snapshot(raw, dataset_id="sub_message")
    by_physical = {field.physical_path: field for field in snapshot.fields}

    assert by_physical["free_text"].mapping_type == "text"
    assert by_physical["free_text.keyword"].is_multifield is True
    assert by_physical["free_text.keyword"].aggregatable is True
    assert by_physical["metadata.provider"].nested_path == "metadata"
    assert by_physical["event_time"].date_format == "strict_date_optional_time||epoch_millis"

    send_attempts = tuple(field for field in snapshot.fields if field.source_path == "send_attempt")
    latencies = tuple(field for field in snapshot.fields if field.source_path == "latency_ms")
    assert (
        infer_compatibility(send_attempts, all_indices=snapshot.indices)
        == MappingCompatibility.COERCIBLE
    )
    assert (
        infer_compatibility(latencies, all_indices=snapshot.indices) == MappingCompatibility.PARTIAL
    )


def test_incompatible_monthly_mapping_is_conflict() -> None:
    raw = json.loads(
        (ROOT / "fixtures" / "opensearch" / "mapping_conflict.json").read_text(encoding="utf-8")
    )
    snapshot = flatten_mapping_snapshot(raw, dataset_id="sub_message")
    variants = tuple(field for field in snapshot.fields if field.source_path == "channel")
    assert (
        infer_compatibility(variants, all_indices=snapshot.indices) == MappingCompatibility.CONFLICT
    )
