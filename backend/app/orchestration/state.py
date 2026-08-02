"""Versioned business state, not an unbounded messages array."""

from typing import TypedDict

from app.contracts.analysis import (
    AnalysisPlan,
    AnalysisPlanDraft,
    ResolvedAnalysis,
    TurnDecision,
)
from app.contracts.dataset import DatasetBundle
from app.contracts.error import StructuredError
from app.contracts.execution import ExecutionRecord, RawSearchResult
from app.contracts.insight import FeatureSummary
from app.contracts.query import CompiledQuery, QueryPlan, QueryPlanDraft
from app.contracts.request import ChatRequest, IdentityContext
from app.contracts.semantic import SemanticCandidateSet
from app.contracts.session import AnswerSnapshot, SessionContext
from app.orchestration.routes import AnalysisRoute


class ChatBIState(TypedDict, total=False):
    request: ChatRequest
    identity: IdentityContext
    correlation_id: str
    turn_id: str
    fixture_id: str
    request_meta: dict[str, object]
    request_policy: str
    request_policy_code: str
    session_context: SessionContext
    turn_decision: TurnDecision
    semantic_candidates: SemanticCandidateSet
    analysis_plan_draft: AnalysisPlanDraft
    repair_attempt: int
    validator_error_codes: tuple[str, ...]
    analysis_plan: AnalysisPlan
    analysis_route: AnalysisRoute
    resolved_analysis: ResolvedAnalysis
    query_plan_draft: QueryPlanDraft
    query_repair_attempt: int
    query_validator_error_codes: tuple[str, ...]
    query_route: str
    query_plan: QueryPlan
    compiled_queries: tuple[CompiledQuery, ...]
    execution_records: tuple[ExecutionRecord, ...]
    raw_results: tuple[RawSearchResult, ...]
    dataset_bundle: DatasetBundle
    feature_summaries: tuple[FeatureSummary, ...]
    phase4_route: str
    answer_snapshot: AnswerSnapshot
    terminal_status: str
    errors: tuple[StructuredError, ...]
