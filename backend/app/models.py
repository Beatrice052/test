from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


IntakeMode = Literal["CREATE_NEW", "EDIT_REFERENCE", "CONFIRM_DIRECTLY"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


class BuildDraftRequest(BaseModel):
    mode: IntakeMode
    requirement: str
    selected_reference_use_case_id: str | None = None


class AnalyzeRequirementRequest(BaseModel):
    requirement: str


class UseCaseCandidate(BaseModel):
    id: str
    name: str
    project: str
    source_system: str
    lob: str
    channel: str
    similarity: str
    badge: str
    reason: str


class ParseAnswerRequest(BaseModel):
    question_id: str
    answer: str


class ApplyPreviewRequest(BaseModel):
    preview_id: str


class UpdateFieldRequest(BaseModel):
    value: Any = ""
    updated_by: str = "USER"


class ExtractedSignals(BaseModel):
    lob: str | None = None
    channel: str | None = None
    trigger: str | None = None
    audience: str | None = None


class ReferenceUseCase(BaseModel):
    id: str
    name: str
    source_system: str
    channel: str
    status: str | None = None


class FieldCandidate(BaseModel):
    field_name: str
    value: Any
    normalized_value: Any = None
    confidence: float = 1.0
    source: Literal["REQUIREMENT_EXTRACTION", "REFERENCE_USE_CASE", "USER_INPUT", "DEFAULT"] = "DEFAULT"
    evidence: str = ""
    reason: str = ""


class GuidedFieldState(BaseModel):
    field_name: str
    display_name: str
    module: str
    domain_object: str
    scope: str
    value: Any = None
    normalized_value: Any = None
    source: Literal[
        "EMPTY",
        "USER_CONFIRMED",
        "USER_INPUT",
        "REQUIREMENT_EXTRACTION",
        "REFERENCE_USE_CASE",
        "DEFAULT",
        "DEPENDENCY_DERIVED",
        "SYSTEM_GENERATED",
    ] = "EMPTY"
    resolution_status: Literal[
        "RESOLVED",
        "RESOLVED_NEEDS_CONFIRMATION",
        "UNRESOLVED_MISSING",
        "UNRESOLVED_LOW_CONFIDENCE",
        "UNRESOLVED_CONFLICT",
        "NOT_APPLICABLE",
    ] = "UNRESOLVED_MISSING"
    ui_status: Literal[
        "EMPTY",
        "PREFILLED",
        "CONFIRMED",
        "NEEDS_CONFIRMATION",
        "CONFLICT",
        "MISSING_REQUIRED",
        "NOT_APPLICABLE",
        "GENERATED",
    ] = "EMPTY"
    required: bool = False
    required_now: bool = False
    applicable: bool = True
    requires_confirmation: bool = False
    blocked_by_fields: list[str] = Field(default_factory=list)
    business_reason: str | None = None
    internal_reason: str | None = None
    help: str = ""
    hidden: bool = False


class InternalImpact(BaseModel):
    impact_id: str = Field(default_factory=lambda: new_id("impact"))
    rule_id: str
    source: str = "dependency_rule_engine"
    trigger_field: str | None = None
    trigger_value: Any = None
    affected_field: str
    old_value: Any = None
    new_value: Any = None
    old_status: str | None = None
    new_status: str | None = None
    old_applicable: bool | None = None
    new_applicable: bool | None = None
    old_required_now: bool | None = None
    new_required_now: bool | None = None
    reason: str
    user_visible: bool = False


class InternalImpactPlan(BaseModel):
    impacts: list[InternalImpact] = Field(default_factory=list)


class UseCaseDomainDraft(BaseModel):
    use_case_master: dict[str, Any] = Field(default_factory=dict)
    use_case_extension: dict[str, Any] = Field(default_factory=dict)
    use_case_channel_rule_list: list[dict[str, Any]] = Field(default_factory=list)
    opt_in_policy: dict[str, Any] = Field(default_factory=dict)
    bounce_back_policy: dict[str, Any] = Field(default_factory=dict)


class GuidedDraftState(BaseModel):
    mode: IntakeMode
    raw_requirement: str
    field_states: dict[str, GuidedFieldState]
    reference_snapshot: dict[str, Any] | None = None
    diff_from_reference: list[dict[str, Any]] = Field(default_factory=list)
    domain_draft: UseCaseDomainDraft = Field(default_factory=UseCaseDomainDraft)
    validation_issues: list[dict[str, Any]] = Field(default_factory=list)
    internal_impact_plan: InternalImpactPlan = Field(default_factory=InternalImpactPlan)


class ActiveQuestionState(BaseModel):
    question_id: str
    group_id: str
    intent_type: str
    title: str
    question: str
    question_type: Literal["FREE_TEXT", "SINGLE_CHOICE", "MULTI_CHOICE", "CONFIRMATION", "STRUCTURED_CHANNEL_RULE"]
    focus_fields: list[str]
    related_fields: list[str] = Field(default_factory=list)
    options: list[dict[str, str]] = Field(default_factory=list)
    why_asking: str = ""
    answer_hints: list[str] = Field(default_factory=list)
    priority_score: float = 0


class ActionPreviewUpdate(BaseModel):
    field_name: str
    display_name: str
    old_value: str
    new_value: str
    reason: str


class StoredActionPreview(BaseModel):
    preview_id: str = Field(default_factory=lambda: new_id("preview"))
    direct_updates: dict[str, Any] = Field(default_factory=dict)
    user_facing_updates: list[ActionPreviewUpdate] = Field(default_factory=list)
    internal_impact_plan: InternalImpactPlan = Field(default_factory=InternalImpactPlan)
    follow_up_summary: str | None = None
    created_at: datetime = Field(default_factory=now_utc)


class BlockingIssue(BaseModel):
    field_name: str
    display_name: str
    message: str


class ValidationResult(BaseModel):
    ready_for_ac: bool = False
    blocking_issues: list[BlockingIssue] = Field(default_factory=list)
    warnings: list[BlockingIssue] = Field(default_factory=list)


class AssistantCard(BaseModel):
    type: str
    title: str
    body: str | None = None
    group_id: str | None = None
    question_id: str | None = None
    question: str | None = None
    question_type: str | None = None
    options: list[dict[str, str]] | None = None
    focus_fields: list[str] | None = None
    why_asking: str | None = None
    priority: str | None = None
    action_preview: dict[str, Any] | None = None
    ready_for_ac: bool | None = None


class GuidedIntakeSession(BaseModel):
    intake_id: str
    mode: IntakeMode
    raw_requirement: str
    selected_reference_use_case_id: str | None = None
    draft_state: GuidedDraftState
    active_question_state: ActiveQuestionState | None = None
    current_action_preview: StoredActionPreview | None = None
    validation_state: ValidationResult | None = None
    assistant_cards: list[AssistantCard] = Field(default_factory=list)
    audit_log: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class FormField(BaseModel):
    name: str
    displayName: str
    value: str = ""
    status: str
    source: str
    help: str
    required: bool = False
    hidden: bool = False
    options: list[dict[str, Any]] = Field(default_factory=list)


class FormModule(BaseModel):
    id: str
    title: str
    complete: int
    total: int
    fields: list[FormField]


class BuildDraftResponse(BaseModel):
    intake_id: str
    mode: IntakeMode
    requirement: str
    extracted_signals: ExtractedSignals
    selected_reference: ReferenceUseCase | None = None
    modules: dict[str, FormModule]
    assistant_cards: list[AssistantCard]
    validation: ValidationResult


class AnalyzeRequirementResponse(BaseModel):
    intake_id: str
    requirement: str
    extracted_signals: ExtractedSignals
    candidates: list[UseCaseCandidate]
    assistant_cards: list[AssistantCard]


class ParseAnswerResponse(BaseModel):
    user_message: str
    assistant_cards: list[AssistantCard]


class ApplyPreviewResponse(BaseModel):
    modules: dict[str, FormModule]
    assistant_cards: list[AssistantCard]
    validation: ValidationResult


class ExportForAcResponse(BaseModel):
    ready_for_ac: bool
    confirmed_use_case: dict[str, Any]
    semantic_summary: str
