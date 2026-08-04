"""Intent, analyst planning, and deterministic resolution contracts."""

from enum import StrEnum
from typing import Literal

from pydantic import Field

from app.contracts.common import Identifier, StrictModel, TimeRange, VersionedModel
from app.contracts.semantic import FieldMaturity, MappingCompatibility, SemanticType

type GovernedChartType = Literal[
    "bar",
    "line",
    "heatmap",
    "stacked_bar",
    "donut",
    "dot",
    "pareto",
    "table",
    "pivot",
]

GOVERNED_CHART_TYPES: tuple[GovernedChartType, ...] = (
    "bar",
    "line",
    "heatmap",
    "stacked_bar",
    "donut",
    "dot",
    "pareto",
    "table",
    "pivot",
)


class TurnKind(StrEnum):
    NEW_ANALYSIS = "NEW_ANALYSIS"
    CLARIFICATION = "CLARIFICATION"
    FILTER_CHANGE = "FILTER_CHANGE"
    TIME_CHANGE = "TIME_CHANGE"
    DIMENSION_CHANGE = "DIMENSION_CHANGE"
    PRESENTATION_CHANGE = "PRESENTATION_CHANGE"
    EXPLANATION = "EXPLANATION"
    NEW_TOPIC = "NEW_TOPIC"


class AnswerStatus(StrEnum):
    ANSWERED = "ANSWERED"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    UNANSWERABLE = "UNANSWERABLE"
    EMPTY = "EMPTY"
    PARTIAL = "PARTIAL"
    FORBIDDEN = "FORBIDDEN"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class FilterIntent(StrictModel):
    field_id: Identifier
    operator: Literal["eq", "in", "range", "exists", "not"]
    values: tuple[str | int | float | bool, ...] = ()


class AnalysisScope(StrictModel):
    dataset_ids: tuple[Identifier, ...]
    time_range: TimeRange
    filters: tuple[FilterIntent, ...] = ()


class MetricDecision(StrictModel):
    metric_id: Identifier
    decision: Literal["required", "recommended", "optional", "rejected", "downgraded"]
    role: str
    reason: str
    rejection_code: str | None = None
    required_capabilities: tuple[str, ...] = ()
    confidence: float = Field(ge=0, le=1)


class AnalyticalTask(StrictModel):
    task_id: Identifier
    analytical_question: str
    analysis_type: str
    priority: Literal["required", "recommended", "optional"]
    metric_ids: tuple[Identifier, ...] = ()
    dimension_ids: tuple[Identifier, ...] = ()
    grain: tuple[str, ...] = ()
    statistical_method_ids: tuple[Identifier, ...] = ()
    visualization_intents: tuple[str, ...] = ()
    business_value: str
    drop_conditions: tuple[str, ...] = ()


class PresentationPreference(StrictModel):
    """A user presentation request interpreted by Agent A, not by the renderer."""

    requested_chart_type: GovernedChartType | None = None
    user_specified: bool = False
    unsupported_chart_label: str | None = None


class AnalysisBudget(StrictModel):
    max_queries: int = Field(default=3, ge=1, le=10)
    max_buckets: int = Field(default=5000, ge=1)
    max_blocks: int = Field(default=8, ge=1, le=20)


class Clarification(StrictModel):
    question: str
    reason_code: str
    allowed_answers: tuple[str, ...] = ()


class AnalysisPlanDraft(StrictModel):
    analysis_goal: str
    question_archetype: str
    turn_relation: TurnKind
    scope: AnalysisScope
    metric_decisions: tuple[MetricDecision, ...]
    tasks: tuple[AnalyticalTask, ...]
    presentation_preference: PresentationPreference = Field(default_factory=PresentationPreference)
    clarification: Clarification | None = None
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    budget: AnalysisBudget = Field(default_factory=AnalysisBudget)


class AnalysisPlan(VersionedModel):
    analysis_goal: str
    question_archetype: str
    turn_relation: TurnKind
    scope: AnalysisScope
    metric_decisions: tuple[MetricDecision, ...]
    tasks: tuple[AnalyticalTask, ...]
    presentation_preference: PresentationPreference = Field(default_factory=PresentationPreference)
    clarification: Clarification | None = None
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    budget: AnalysisBudget = Field(default_factory=AnalysisBudget)


class TurnDecision(VersionedModel):
    turn_kind: TurnKind
    execution_mode: Literal["new_query", "reuse", "requery", "clarify", "reject"]
    analytical_base_answer_id: str | None = None
    reason_codes: tuple[str, ...] = ()


class ResolvedFilter(StrictModel):
    field_id: Identifier
    physical_path: str
    operator: str
    values: tuple[str | int | float | bool, ...]
    value_dictionary_id: Identifier | None = None


class ResolvedMetric(StrictModel):
    metric_id: Identifier
    version: str
    required_field_ids: tuple[Identifier, ...]
    required_grain: tuple[str, ...]
    executable: bool
    reason: str | None = None


class ResolvedFieldDescriptor(StrictModel):
    """Bounded semantic facts supplied to Agent B; never a physical field binding."""

    field_id: Identifier
    dataset_id: Identifier
    display_name: str
    description: str | None = None
    aliases: tuple[str, ...] = ()
    business_domain: str | None = None
    mapping_type: str
    semantic_type: SemanticType
    maturity: FieldMaturity
    capabilities: tuple[str, ...]
    compatibility: MappingCompatibility
    cardinality_estimate: int | None = Field(default=None, ge=0)
    cardinality_approximate: bool = False


class ResolvedAnalysis(VersionedModel):
    analysis_plan_id: str
    dataset_ids: tuple[Identifier, ...]
    index_patterns: tuple[str, ...]
    resolved_field_ids: tuple[Identifier, ...]
    field_descriptors: tuple[ResolvedFieldDescriptor, ...]
    metrics: tuple[ResolvedMetric, ...]
    filters: tuple[ResolvedFilter, ...]
    time_field_id: Identifier
    time_range: TimeRange
    policy_scope_id: Identifier
    method_ids: tuple[Identifier, ...] = ()
    answerable: bool
    caveats: tuple[str, ...] = ()
