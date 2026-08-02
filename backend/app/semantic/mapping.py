"""OpenSearch Mapping flattening and snapshot normalization."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.contracts.common import Provenance, semantic_hash
from app.contracts.semantic import MappingField, MappingSnapshot

AGGREGATABLE_TYPES = {
    "keyword",
    "date",
    "integer",
    "long",
    "short",
    "byte",
    "double",
    "float",
    "half_float",
    "scaled_float",
    "boolean",
    "ip",
}
SORTABLE_TYPES = AGGREGATABLE_TYPES
SEARCHABLE_TYPES = AGGREGATABLE_TYPES | {"text", "match_only_text"}


class MappingFormatError(ValueError):
    pass


def _extract_indices(raw: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]], datetime]:
    captured_raw = raw.get("captured_at")
    captured_at = (
        datetime.fromisoformat(str(captured_raw).replace("Z", "+00:00"))
        if captured_raw
        else datetime.now(UTC)
    )
    if "indices" in raw and isinstance(raw["indices"], Mapping):
        indices = dict(raw["indices"])
    elif "mappings" in raw:
        index_name = str(raw.get("index", "snapshot_index"))
        indices = {index_name: raw}
    else:
        indices = {
            str(name): body
            for name, body in raw.items()
            if isinstance(body, Mapping) and "mappings" in body
        }
    if not indices:
        raise MappingFormatError("mapping snapshot contains no indices")
    return indices, captured_at


def _walk_properties(
    properties: Mapping[str, Any],
    *,
    index_name: str,
    prefix: str = "",
    parent_object_path: str | None = None,
    nested_path: str | None = None,
) -> list[MappingField]:
    fields: list[MappingField] = []
    for name in sorted(properties):
        definition = properties[name]
        if not isinstance(definition, Mapping):
            continue
        path = f"{prefix}.{name}" if prefix else name
        mapping_type = str(definition.get("type") or "object")
        current_nested_path = path if mapping_type == "nested" else nested_path
        fields.append(
            MappingField(
                source_path=path,
                physical_path=path,
                mapping_type=mapping_type,
                parent_object_path=parent_object_path,
                nested_path=current_nested_path,
                is_multifield=False,
                searchable=mapping_type in SEARCHABLE_TYPES,
                aggregatable=mapping_type in AGGREGATABLE_TYPES,
                sortable=mapping_type in SORTABLE_TYPES,
                date_format=str(definition["format"]) if definition.get("format") else None,
                observed_in_indices=(index_name,),
            )
        )
        sub_properties = definition.get("properties")
        if isinstance(sub_properties, Mapping) and definition.get("enabled", True) is not False:
            fields.extend(
                _walk_properties(
                    sub_properties,
                    index_name=index_name,
                    prefix=path,
                    parent_object_path=path,
                    nested_path=current_nested_path,
                )
            )
        multi_fields = definition.get("fields")
        if isinstance(multi_fields, Mapping):
            for sub_name in sorted(multi_fields):
                sub_definition = multi_fields[sub_name]
                if not isinstance(sub_definition, Mapping):
                    continue
                sub_type = str(sub_definition.get("type", "keyword"))
                fields.append(
                    MappingField(
                        source_path=path,
                        physical_path=f"{path}.{sub_name}",
                        mapping_type=sub_type,
                        parent_object_path=parent_object_path,
                        nested_path=current_nested_path,
                        is_multifield=True,
                        searchable=sub_type in SEARCHABLE_TYPES,
                        aggregatable=sub_type in AGGREGATABLE_TYPES,
                        sortable=sub_type in SORTABLE_TYPES,
                        date_format=(
                            str(sub_definition["format"]) if sub_definition.get("format") else None
                        ),
                        observed_in_indices=(index_name,),
                    )
                )
    return fields


def flatten_mapping_snapshot(raw: Mapping[str, Any], *, dataset_id: str) -> MappingSnapshot:
    indices, captured_at = _extract_indices(raw)
    flattened: list[MappingField] = []
    for index_name, body in sorted(indices.items()):
        mappings = body.get("mappings", body)
        properties = mappings.get("properties", {}) if isinstance(mappings, Mapping) else {}
        if not isinstance(properties, Mapping):
            raise MappingFormatError(f"index {index_name} mappings.properties is invalid")
        flattened.extend(_walk_properties(properties, index_name=index_name))

    grouped: dict[tuple[object, ...], list[MappingField]] = defaultdict(list)
    for field in flattened:
        key = (
            field.source_path,
            field.physical_path,
            field.mapping_type,
            field.parent_object_path,
            field.nested_path,
            field.is_multifield,
            field.date_format,
        )
        grouped[key].append(field)

    merged: list[MappingField] = []
    for group_key in sorted(grouped, key=lambda item: (str(item[1]), str(item[2]))):
        variants = grouped[group_key]
        first = variants[0]
        merged.append(
            first.model_copy(
                update={
                    "observed_in_indices": tuple(
                        sorted({index for item in variants for index in item.observed_in_indices})
                    )
                }
            )
        )

    raw_hash = semantic_hash(raw, exclude_keys=frozenset({"captured_at"}))
    payload = [field.model_dump(mode="json") for field in merged]
    content_hash = semantic_hash(payload)
    return MappingSnapshot(
        object_id=f"mps_{content_hash.removeprefix('sha256:')[:16]}",
        created_at=captured_at,
        content_hash=content_hash,
        provenance=Provenance(producer="semantic.mapping", source_hashes={"raw": raw_hash}),
        dataset_id=dataset_id,
        captured_at=captured_at,
        indices=tuple(sorted(indices)),
        fields=tuple(merged),
        raw_mapping_hash=raw_hash,
    )
