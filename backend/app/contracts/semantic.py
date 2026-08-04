"""Semantic catalog, mapping, retrieval, and compilation contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from app.contracts.common import (
    Identifier,
    JsonScalar,
    JsonValue,
    Sha256,
    StrictModel,
    VersionedModel,
)


class FieldMaturity(StrEnum):
    MAPPING_ONLY = "MAPPING_ONLY"
    DOCUMENTED = "DOCUMENTED"
    PROFILED = "PROFILED"
    BUSINESS_CONFIRMED = "BUSINESS_CONFIRMED"
    BLOCKED = "BLOCKED"


class MappingCompatibility(StrEnum):
    EXACT = "EXACT"
    COERCIBLE = "COERCIBLE"
    PARTIAL = "PARTIAL"
    CONFLICT = "CONFLICT"


class SemanticType(StrEnum):
    CATEGORICAL_DIMENSION = "categorical_dimension"
    TIME_DIMENSION = "time_dimension"
    NUMERIC_MEASURE = "numeric_measure"
    IDENTIFIER = "identifier"
    BOOLEAN_DIMENSION = "boolean_dimension"
    FREE_TEXT = "free_text"
    UNKNOWN = "unknown"


class FieldSecurity(StrictModel):
    classification: Literal["public", "internal", "confidential", "restricted"] = "internal"
    aggregatable: bool = True
    detail_visible: bool = False
    model_visible: bool = True


class CardinalityProfile(StrictModel):
    estimate: int | None = Field(default=None, ge=0)
    approximate: bool = False
    profiled_at: datetime | None = None


class FieldProvenance(StrictModel):
    mapping_hash: Sha256
    catalog_row: int | None = Field(default=None, ge=1)
    owner: str | None = Field(default=None, max_length=256)
    sanitized: bool = False


class MappingField(StrictModel):
    source_path: str = Field(min_length=1, max_length=512)
    physical_path: str = Field(min_length=1, max_length=512)
    mapping_type: str = Field(min_length=1, max_length=64)
    parent_object_path: str | None = None
    nested_path: str | None = None
    is_multifield: bool = False
    searchable: bool = False
    aggregatable: bool = False
    sortable: bool = False
    date_format: str | None = None
    observed_in_indices: tuple[str, ...]


class MappingSnapshot(VersionedModel):
    dataset_id: Identifier
    captured_at: datetime
    indices: tuple[str, ...]
    fields: tuple[MappingField, ...]
    raw_mapping_hash: Sha256


class FieldProfile(StrictModel):
    """Bounded aggregate profile; it never contains raw OpenSearch documents."""

    source_path: str = Field(min_length=1, max_length=512)
    physical_path: str = Field(min_length=1, max_length=512)
    mapping_type: str = Field(min_length=1, max_length=64)
    document_count: int = Field(ge=0)
    non_null_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    cardinality_estimate: int | None = Field(default=None, ge=0)
    cardinality_approximate: bool = True
    sample_values: tuple[JsonScalar, ...] = Field(default=(), max_length=10)
    minimum: JsonScalar = None
    maximum: JsonScalar = None


class FieldProfileSnapshot(VersionedModel):
    dataset_id: Identifier
    captured_at: datetime
    indices: tuple[str, ...]
    mapping_content_hash: Sha256
    fields: tuple[FieldProfile, ...]
    profile_query_hash: Sha256


class FieldDescriptionRow(StrictModel):
    field_path: str = Field(min_length=1, max_length=512)
    description: str = Field(min_length=1, max_length=2000)
    aliases: tuple[str, ...] = ()
    business_domain: str | None = Field(default=None, max_length=128)
    usage_guidance: str | None = Field(default=None, max_length=1000)
    value_meaning: str | None = Field(default=None, max_length=1000)
    metric_caveat: str | None = Field(default=None, max_length=1000)
    sensitivity: str | None = Field(default=None, max_length=64)
    owner: str | None = Field(default=None, max_length=256)
    confirmed: bool = False
    source_row: int = Field(ge=2)
    original_description_hash: Sha256
    sanitizer_events: tuple[str, ...] = ()


class CanonicalField(VersionedModel):
    field_id: Identifier
    dataset_id: Identifier
    physical_path: str
    source_path: str
    mapping_type: str
    semantic_type: SemanticType
    display_name: str
    description: str | None = None
    aliases: tuple[str, ...] = ()
    business_domain: str | None = None
    maturity: FieldMaturity
    capabilities: tuple[str, ...]
    compatibility: MappingCompatibility
    cardinality: CardinalityProfile = Field(default_factory=CardinalityProfile)
    security: FieldSecurity = Field(default_factory=FieldSecurity)
    field_provenance: FieldProvenance
    observed_in_indices: tuple[str, ...]


class ImportIssue(StrictModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    severity: Literal["INFO", "WARNING", "ERROR", "FATAL"]
    message: str = Field(min_length=1, max_length=1000)
    field_path: str | None = None
    source_row: int | None = Field(default=None, ge=1)
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ImportReport(VersionedModel):
    status: Literal["PASSED", "PASSED_WITH_WARNINGS", "FAILED"]
    mapping_field_count: int = Field(ge=0)
    catalog_row_count: int = Field(ge=0)
    matched_count: int = Field(ge=0)
    mapping_only_fields: tuple[str, ...] = ()
    catalog_only_fields: tuple[str, ...] = ()
    duplicate_field_paths: tuple[str, ...] = ()
    ambiguous_rows: tuple[int, ...] = ()
    type_conflicts: tuple[str, ...] = ()
    invalid_metric_bindings: tuple[str, ...] = ()
    blocked_fields: tuple[str, ...] = ()
    sanitized_descriptions: tuple[str, ...] = ()
    mapping_hash: Sha256
    catalog_hash: Sha256
    issues: tuple[ImportIssue, ...] = ()


class DatasetDefinition(StrictModel):
    dataset_id: Identifier
    display_name: str
    index_pattern: str
    default_timezone: str
    primary_time_field_id: Identifier
    description: str | None = None
    missing_index_policy: Literal["empty", "error"] = "empty"


class PolicyDefinition(StrictModel):
    policy_id: Identifier
    version: str
    allowed_dataset_ids: tuple[Identifier, ...]
    allowed_index_patterns: tuple[str, ...]
    blocked_field_ids: tuple[Identifier, ...] = ()
    sensitive_field_ids: tuple[Identifier, ...] = ()
    detail_allowed_field_ids: tuple[Identifier, ...] = ()
    max_detail_hits: int = Field(default=100, ge=0, le=1000)
    max_total_buckets: int = Field(default=5000, ge=1)
    scripts_allowed: bool = False


class CandidateItem(StrictModel):
    item_id: Identifier
    item_type: Literal["dataset", "metric", "field", "recipe", "method", "value"]
    display_name: str
    summary: str
    score: float
    capabilities: tuple[str, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class SemanticCandidateSet(VersionedModel):
    query: str
    dataset_candidates: tuple[CandidateItem, ...] = ()
    metric_candidates: tuple[CandidateItem, ...] = ()
    field_candidates: tuple[CandidateItem, ...] = ()
    recipe_candidates: tuple[CandidateItem, ...] = ()
    method_candidates: tuple[CandidateItem, ...] = ()
    value_candidates: tuple[CandidateItem, ...] = ()
    retrieval_version: str


class SemanticManifest(VersionedModel):
    package_version: str
    compiled_at: datetime
    dataset_ids: tuple[Identifier, ...]
    file_hashes: dict[str, Sha256]
    mapping_hash: Sha256
    catalog_hash: Sha256
    registry_hash: Sha256
    fts_schema_version: str = "1"
