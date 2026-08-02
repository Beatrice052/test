"""Canonical hash and semantic field diff tests."""

from pathlib import Path

from app.contracts.common import semantic_hash
from app.semantic.diff import diff_fields
from app.semantic.package import CompiledSemanticPackage

ROOT = Path(__file__).resolve().parents[4]


def test_semantic_hash_is_order_stable_and_can_exclude_non_semantic_time() -> None:
    left = {"value": {"b": 2, "a": 1}, "captured_at": "first"}
    right = {"captured_at": "second", "value": {"a": 1, "b": 2}}

    assert semantic_hash(left, exclude_keys=frozenset({"captured_at"})) == semantic_hash(
        right, exclude_keys=frozenset({"captured_at"})
    )


def test_field_diff_reports_add_remove_and_physical_change() -> None:
    fields = CompiledSemanticPackage(ROOT / "compiled-semantic" / "mock").fields()
    previous = fields[:2]
    changed = previous[0].model_copy(update={"physical_path": "changed.keyword"})
    current = (changed, fields[2])

    result = diff_fields(previous, current)

    assert result.physical_changes == (previous[0].field_id,)
    assert result.removed == (previous[1].field_id,)
    assert result.added == (fields[2].field_id,)
