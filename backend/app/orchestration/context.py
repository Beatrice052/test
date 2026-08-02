"""Deterministic session inheritance boundaries around Agent A turn classification."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from app.contracts.analysis import AnswerStatus, TurnDecision, TurnKind
from app.contracts.common import Provenance, semantic_hash
from app.contracts.request import ChatRequest
from app.contracts.session import ActiveAnalyticalContext, SessionContext
from app.persistence.ids import new_id


class ContextTurnRouter:
    def decide(
        self,
        request: ChatRequest,
        session: SessionContext,
        *,
        latest_answer_status: AnswerStatus | None = None,
    ) -> TurnDecision:
        """Create only a provisional hint; Agent A remains the turn-intent authority."""

        del request
        if latest_answer_status == AnswerStatus.CLARIFICATION_REQUIRED:
            kind = TurnKind.CLARIFICATION
        else:
            kind = TurnKind.NEW_ANALYSIS
        mode: Literal["new_query", "reuse", "requery", "clarify", "reject"] = (
            "requery" if kind == TurnKind.CLARIFICATION else "new_query"
        )
        payload = {
            "session_id": session.object_id,
            "turn_kind": kind,
            "execution_mode": mode,
            "base": session.active_context.analytical_base_answer_id,
            "provisional": True,
        }
        return TurnDecision(
            object_id=new_id("td"),
            created_at=datetime.now(UTC),
            content_hash=semantic_hash(payload),
            provenance=Provenance(producer="orchestration.context_router"),
            turn_kind=kind,
            execution_mode=mode,
            analytical_base_answer_id=(
                session.active_context.analytical_base_answer_id
                if kind
                in {
                    TurnKind.FILTER_CHANGE,
                    TurnKind.TIME_CHANGE,
                    TurnKind.DIMENSION_CHANGE,
                    TurnKind.PRESENTATION_CHANGE,
                    TurnKind.EXPLANATION,
                    TurnKind.CLARIFICATION,
                }
                else None
            ),
            reason_codes=("PENDING_AGENT_A_CLASSIFICATION",),
        )

    def finalize(self, turn_kind: TurnKind, session: SessionContext) -> TurnDecision:
        """Map Agent A's semantic turn decision to a safe execution route."""

        if session.latest_answer_id is None and turn_kind not in {
            TurnKind.NEW_ANALYSIS,
            TurnKind.NEW_TOPIC,
        }:
            raise ValueError("follow-up turn requires an analytical base answer")
        mode_by_kind: dict[
            TurnKind, Literal["new_query", "reuse", "requery", "clarify", "reject"]
        ] = {
            TurnKind.NEW_ANALYSIS: "new_query",
            TurnKind.NEW_TOPIC: "new_query",
            TurnKind.CLARIFICATION: "requery",
            TurnKind.FILTER_CHANGE: "requery",
            TurnKind.TIME_CHANGE: "requery",
            TurnKind.DIMENSION_CHANGE: "requery",
            TurnKind.PRESENTATION_CHANGE: "reuse",
            TurnKind.EXPLANATION: "reuse",
        }
        mode = mode_by_kind[turn_kind]
        base_answer_id = (
            session.active_context.analytical_base_answer_id or session.latest_answer_id
            if turn_kind
            not in {
                TurnKind.NEW_ANALYSIS,
                TurnKind.NEW_TOPIC,
            }
            else None
        )
        payload = {
            "session_id": session.object_id,
            "turn_kind": turn_kind,
            "execution_mode": mode,
            "base": base_answer_id,
            "provisional": False,
        }
        return TurnDecision(
            object_id=new_id("td"),
            created_at=datetime.now(UTC),
            content_hash=semantic_hash(payload),
            provenance=Provenance(producer="orchestration.context_router"),
            turn_kind=turn_kind,
            execution_mode=mode,
            analytical_base_answer_id=base_answer_id,
            reason_codes=(f"AGENT_A_{turn_kind.value}",),
        )

    @staticmethod
    def require_requery(decision: TurnDecision) -> TurnDecision:
        """Fail safe when a claimed reuse turn changes the analytical data signature."""

        payload = {
            "source_decision_id": decision.object_id,
            "turn_kind": decision.turn_kind,
            "execution_mode": "requery",
            "base": decision.analytical_base_answer_id,
            "reason": "REUSE_DATA_SIGNATURE_CHANGED",
        }
        return TurnDecision(
            object_id=new_id("td"),
            created_at=datetime.now(UTC),
            content_hash=semantic_hash(payload),
            provenance=Provenance(
                producer="orchestration.context_router.reuse_guard",
                source_ids=(decision.object_id,),
            ),
            turn_kind=decision.turn_kind,
            execution_mode="requery",
            analytical_base_answer_id=decision.analytical_base_answer_id,
            reason_codes=(*decision.reason_codes, "REUSE_DATA_SIGNATURE_CHANGED"),
        )

    @staticmethod
    def planner_context(session: SessionContext, decision: TurnDecision) -> ActiveAnalyticalContext:
        del decision
        return (
            session.active_context
            if session.latest_answer_id is not None
            else ActiveAnalyticalContext()
        )
