"""Authoritative, versioned cross-layer contracts."""

from app.contracts.analysis import (
    AnalysisPlan,
    AnalysisPlanDraft,
    ResolvedAnalysis,
    TurnDecision,
)
from app.contracts.dashboard import (
    DashboardSpec,
    VisualizationCandidate,
    VisualizationDefinition,
)
from app.contracts.dataset import DataQARecord, DatasetBundle, DatasetContract, TabularDataset
from app.contracts.error import StructuredError
from app.contracts.evidence import EvidencePackage
from app.contracts.execution import ExecutionRecord, RawSearchResult
from app.contracts.insight import ClaimDraft, ClaimSpec, FeatureSummary
from app.contracts.metric import (
    AnalysisRecipe,
    FormulaNode,
    MethodDefinition,
    MetricDefinition,
    MetricValue,
    ValueDictionary,
)
from app.contracts.progress import AnalysisProgressEvent
from app.contracts.query import CompiledQuery, QueryPlan, QueryPlanDraft
from app.contracts.request import ChatRequest, IdentityContext
from app.contracts.semantic import (
    CanonicalField,
    DatasetDefinition,
    FieldDescriptionRow,
    ImportReport,
    MappingSnapshot,
    PolicyDefinition,
    SemanticCandidateSet,
    SemanticManifest,
)
from app.contracts.session import AnswerSnapshot, SessionContext

SCHEMA_MODELS = (
    ChatRequest,
    IdentityContext,
    SessionContext,
    TurnDecision,
    SemanticCandidateSet,
    AnalysisPlanDraft,
    AnalysisPlan,
    ResolvedAnalysis,
    QueryPlanDraft,
    QueryPlan,
    CompiledQuery,
    ExecutionRecord,
    RawSearchResult,
    DatasetContract,
    TabularDataset,
    DatasetBundle,
    MetricDefinition,
    MetricValue,
    DataQARecord,
    FeatureSummary,
    ClaimDraft,
    ClaimSpec,
    VisualizationCandidate,
    DashboardSpec,
    EvidencePackage,
    AnswerSnapshot,
    StructuredError,
    ImportReport,
    CanonicalField,
    SemanticManifest,
    MappingSnapshot,
    FieldDescriptionRow,
    DatasetDefinition,
    PolicyDefinition,
    FormulaNode,
    ValueDictionary,
    MethodDefinition,
    AnalysisRecipe,
    VisualizationDefinition,
    AnalysisProgressEvent,
)

CORE_CONTRACTS = SCHEMA_MODELS[:19]

__all__ = ["CORE_CONTRACTS", "SCHEMA_MODELS"]
