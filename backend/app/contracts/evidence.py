"""Evidence package and access-layer contracts."""

from pydantic import Field

from app.contracts.common import JsonValue, StrictModel, VersionedModel


class BusinessEvidence(StrictModel):
    scope: dict[str, JsonValue]
    metric_definitions: tuple[dict[str, JsonValue], ...] = ()
    data_tables: tuple[str, ...] = ()
    reconciliations: tuple[dict[str, JsonValue], ...] = ()
    quality: tuple[dict[str, JsonValue], ...] = ()
    downloads: tuple[str, ...] = ()


class AdvancedEvidence(StrictModel):
    query_plan: dict[str, JsonValue]
    compiled_queries: tuple[dict[str, JsonValue], ...] = ()
    execution_summaries: tuple[dict[str, JsonValue], ...] = ()
    result_contracts: tuple[dict[str, JsonValue], ...] = ()


class EvidenceRedaction(StrictModel):
    removed_fields: tuple[str, ...] = ()
    masked_fields: tuple[str, ...] = ()
    policy_id: str | None = None


class EvidencePackage(VersionedModel):
    business: BusinessEvidence
    advanced: AdvancedEvidence
    debug_ref: str | None = None
    redaction: EvidenceRedaction = Field(default_factory=EvidenceRedaction)
