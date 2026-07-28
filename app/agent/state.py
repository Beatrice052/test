from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.agent.contracts import AnalysisPlan, EvidenceBundle, QueryPlan


class RunStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PLANNED = "PLANNED"
    RESOLVED = "RESOLVED"
    QUERY_READY = "QUERY_READY"
    EXECUTED = "EXECUTED"
    VALIDATED = "VALIDATED"
    PRESENTED = "PRESENTED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    UNSUPPORTED = "UNSUPPORTED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    NO_DATA = "NO_DATA"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    QA_FAILED = "QA_FAILED"


class AgentState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    _terminal: ClassVar[set[RunStatus]] = {
        RunStatus.PRESENTED,
        RunStatus.NEEDS_CLARIFICATION,
        RunStatus.UNSUPPORTED,
        RunStatus.POLICY_BLOCKED,
        RunStatus.NO_DATA,
        RunStatus.EXECUTION_FAILED,
        RunStatus.QA_FAILED,
    }
    _transitions: ClassVar[dict[RunStatus, set[RunStatus]]] = {
        RunStatus.RECEIVED: {
            RunStatus.PLANNED,
            RunStatus.NEEDS_CLARIFICATION,
            RunStatus.UNSUPPORTED,
            RunStatus.POLICY_BLOCKED,
        },
        RunStatus.PLANNED: {RunStatus.RESOLVED, RunStatus.NEEDS_CLARIFICATION},
        RunStatus.RESOLVED: {
            RunStatus.QUERY_READY,
            RunStatus.NEEDS_CLARIFICATION,
            RunStatus.UNSUPPORTED,
            RunStatus.POLICY_BLOCKED,
        },
        RunStatus.QUERY_READY: {RunStatus.EXECUTED, RunStatus.EXECUTION_FAILED},
        RunStatus.EXECUTED: {RunStatus.VALIDATED, RunStatus.NO_DATA, RunStatus.QA_FAILED},
        RunStatus.VALIDATED: {RunStatus.PRESENTED},
    }

    run_id: str
    session_id: str
    status: RunStatus = RunStatus.RECEIVED
    user_question: str
    analysis_plan: AnalysisPlan | None = None
    field_resolution: dict[str, Any] | None = None
    metric_resolution: dict[str, Any] | None = None
    answerability: dict[str, Any] | None = None
    query_plans: list[QueryPlan] = Field(default_factory=list)
    compiled_queries: list[dict[str, Any]] = Field(default_factory=list)
    execution_records: list[dict[str, Any]] = Field(default_factory=list)
    raw_results: list[dict[str, Any]] = Field(default_factory=list)
    prepared_data: dict[str, Any] | None = None
    chart_specs: list[dict[str, Any]] = Field(default_factory=list)
    summary: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    semantic_model_version: str = "not-compiled"
    metric_versions: dict[str, str] = Field(default_factory=dict)
    evidence: EvidenceBundle | None = None

    def transition(self, next_status: RunStatus) -> AgentState:
        if self.status in self._terminal:
            raise ValueError(f"terminal state {self.status} cannot transition")
        if next_status not in self._transitions.get(self.status, set()):
            raise ValueError(f"invalid state transition: {self.status} -> {next_status}")
        return self.model_copy(update={"status": next_status}, deep=True)
