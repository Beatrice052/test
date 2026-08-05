"""Deterministic mapping-to-semantic capability inference."""

from collections.abc import Sequence

from app.contracts.semantic import (
    FieldDescriptionRow,
    MappingCompatibility,
    MappingField,
    SemanticType,
)

NUMERIC_TYPES = {"byte", "short", "integer", "long", "half_float", "float", "double"}

AGGREGATION_CAPABILITIES = {
    "value_count": "aggregate_value_count",
    "cardinality": "aggregate_cardinality",
    "sum": "aggregate_sum",
    "avg": "aggregate_avg",
    "min": "aggregate_min",
    "max": "aggregate_max",
    "stats": "aggregate_stats",
    "extended_stats": "aggregate_extended_stats",
    "percentiles": "aggregate_percentiles",
}


def choose_mapping_variant(variants: Sequence[MappingField]) -> MappingField:
    if not variants:
        raise ValueError("at least one mapping variant is required")
    aggregatable_multifields = [
        field for field in variants if field.is_multifield and field.aggregatable
    ]
    if aggregatable_multifields:
        return sorted(aggregatable_multifields, key=lambda item: item.physical_path)[0]
    aggregatable = [field for field in variants if field.aggregatable]
    if aggregatable:
        return sorted(aggregatable, key=lambda item: item.physical_path)[0]
    return sorted(variants, key=lambda item: item.physical_path)[0]


def infer_compatibility(
    variants: Sequence[MappingField], *, all_indices: Sequence[str]
) -> MappingCompatibility:
    observed = {index for field in variants for index in field.observed_in_indices}
    types = {field.mapping_type for field in variants if not field.is_multifield}
    if not types:
        types = {field.mapping_type for field in variants}
    nested_paths = {field.nested_path for field in variants}
    if len(nested_paths) > 1:
        return MappingCompatibility.CONFLICT
    if len(types) > 1 and not types.issubset(NUMERIC_TYPES):
        return MappingCompatibility.CONFLICT
    if observed != set(all_indices):
        return MappingCompatibility.PARTIAL
    if len(types) > 1:
        return MappingCompatibility.COERCIBLE
    return MappingCompatibility.EXACT


def infer_semantic_type(
    field: MappingField, description: FieldDescriptionRow | None
) -> SemanticType:
    domain = (description.business_domain or "").lower() if description else ""
    if field.mapping_type == "date" or domain in {"time", "date", "时间"}:
        return SemanticType.TIME_DIMENSION
    if field.mapping_type in NUMERIC_TYPES:
        return SemanticType.NUMERIC_MEASURE
    if field.mapping_type == "boolean":
        return SemanticType.BOOLEAN_DIMENSION
    if field.mapping_type in {"text", "match_only_text"} and not field.aggregatable:
        return SemanticType.FREE_TEXT
    if field.source_path.endswith("_id") or field.source_path.endswith(".id"):
        return SemanticType.IDENTIFIER
    if field.mapping_type == "keyword" or field.aggregatable:
        return SemanticType.CATEGORICAL_DIMENSION
    return SemanticType.UNKNOWN


def infer_capabilities(variants: Sequence[MappingField]) -> tuple[str, ...]:
    capabilities: set[str] = set()
    if any(field.searchable for field in variants):
        capabilities.add("filter")
    if any(field.mapping_type in {"text", "match_only_text"} for field in variants):
        capabilities.add("full_text")
    if any(field.aggregatable for field in variants):
        capabilities.update(
            {
                "group_by",
                "top_n",
                AGGREGATION_CAPABILITIES["value_count"],
                AGGREGATION_CAPABILITIES["cardinality"],
            }
        )
    if any(field.sortable for field in variants):
        capabilities.add("sort")
    if any(field.mapping_type == "date" for field in variants):
        capabilities.update(
            {
                "range",
                "date_histogram",
                AGGREGATION_CAPABILITIES["min"],
                AGGREGATION_CAPABILITIES["max"],
            }
        )
    if any(field.mapping_type in NUMERIC_TYPES for field in variants):
        capabilities.update(
            {
                "metric",
                "histogram",
                "range",
                AGGREGATION_CAPABILITIES["sum"],
                AGGREGATION_CAPABILITIES["avg"],
                AGGREGATION_CAPABILITIES["min"],
                AGGREGATION_CAPABILITIES["max"],
                AGGREGATION_CAPABILITIES["stats"],
                AGGREGATION_CAPABILITIES["extended_stats"],
                AGGREGATION_CAPABILITIES["percentiles"],
            }
        )
    if any(field.nested_path for field in variants):
        capabilities.add("nested")
    return tuple(sorted(capabilities))
