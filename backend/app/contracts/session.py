"""Session, turn, immutable answer snapshot, and active context contracts."""

from datetime import datetime

from pydantic import Field

from app.contracts.analysis import AnalysisPlan, AnswerStatus, TurnKind
from app.contracts.common import Identifier, StrictModel, VersionedModel
from app.contracts.dashboard import DashboardSpec
from app.contracts.dataset import DatasetBundle
from app.contracts.evidence import EvidencePackage
from app.contracts.insight import ClaimSpec
from app.contracts.query import QueryPlan


class ActiveAnalyticalContext(StrictModel):
    analytical_base_answer_id: str | None = None
    dataset_ids: tuple[Identifier, ...] = ()
    metric_ids: tuple[Identifier, ...] = ()
    dimension_ids: tuple[Identifier, ...] = ()
    grain: tuple[str, ...] = ()
    filter_summary: tuple[str, ...] = ()
    time_summary: str | None = None


class SessionContext(VersionedModel):
    subject_id: str
    title: str
    version: int = Field(ge=0)
    archived: bool = False
    active_context: ActiveAnalyticalContext = Field(default_factory=ActiveAnalyticalContext)
    latest_answer_id: str | None = None
    updated_at: datetime


class AnswerSnapshot(VersionedModel):
    session_id: str
    chronological_parent_answer_id: str | None = None
    analytical_base_answer_id: str | None = None
    turn_kind: TurnKind
    status: AnswerStatus
    semantic_package_version: str
    metric_versions: tuple[str, ...]
    analysis_plan: AnalysisPlan | None = None
    query_plan: QueryPlan | None = None
    dataset_bundle: DatasetBundle | None = None
    dashboard_spec: DashboardSpec | None = None
    claims: tuple[ClaimSpec, ...] = ()
    evidence_package: EvidencePackage | None = None
    limitations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
