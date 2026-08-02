"""Stable semantic package field diff."""

from dataclasses import dataclass

from app.contracts.semantic import CanonicalField


@dataclass(frozen=True, slots=True)
class SemanticFieldDiff:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    physical_changes: tuple[str, ...]
    type_changes: tuple[str, ...]
    maturity_changes: tuple[str, ...]


def diff_fields(
    previous: tuple[CanonicalField, ...], current: tuple[CanonicalField, ...]
) -> SemanticFieldDiff:
    previous_by_id = {field.field_id: field for field in previous}
    current_by_id = {field.field_id: field for field in current}
    shared = sorted(previous_by_id.keys() & current_by_id.keys())
    return SemanticFieldDiff(
        added=tuple(sorted(current_by_id.keys() - previous_by_id.keys())),
        removed=tuple(sorted(previous_by_id.keys() - current_by_id.keys())),
        physical_changes=tuple(
            field_id
            for field_id in shared
            if previous_by_id[field_id].physical_path != current_by_id[field_id].physical_path
        ),
        type_changes=tuple(
            field_id
            for field_id in shared
            if previous_by_id[field_id].mapping_type != current_by_id[field_id].mapping_type
        ),
        maturity_changes=tuple(
            field_id
            for field_id in shared
            if previous_by_id[field_id].maturity != current_by_id[field_id].maturity
        ),
    )
