"""Phase 2 nodes with one writer per authoritative state field."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from app.agents.analyst_planner import DataAnalystPlannerAgent
from app.contracts.analysis import AnalysisPlan, AnswerStatus
from app.contracts.common import Provenance, semantic_hash
from app.contracts.session import AnswerSnapshot
from app.orchestration.context import ContextTurnRouter
from app.orchestration.planner_validation import (
    AnalysisPlanValidationError,
    AnalysisPlanValidator,
)
from app.orchestration.state import ChatBIState
from app.persistence.answer_repository import AnswerRepository
from app.persistence.ids import new_id
from app.persistence.session_repository import SessionRepository
from app.semantic.resolver import AnalysisPlanResolver
from app.semantic.retriever import SemanticRetriever


class Phase2Nodes:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        answers: AnswerRepository,
        retriever: SemanticRetriever,
        planner: DataAnalystPlannerAgent,
        validator: AnalysisPlanValidator,
        resolver: AnalysisPlanResolver,
        semantic_package_version: str,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.sessions = sessions
        self.answers = answers
        self.retriever = retriever
        self.planner = planner
        self.validator = validator
        self.resolver = resolver
        self.semantic_package_version = semantic_package_version
        self.now = now or (lambda: datetime.now(UTC))
        self.router = ContextTurnRouter()

    def validate_request(self, state: ChatBIState) -> dict[str, object]:
        request = state["request"]
        normalized = request.message.casefold().replace("_", " ")
        forbidden_code = (
            "RAW_DSL_FORBIDDEN"
            if "raw dsl" in normalized or "原始dsl" in normalized
            else "DESTRUCTIVE_OPERATION_FORBIDDEN"
            if any(
                token in normalized
                for token in ("删除索引", "delete index", "drop index", "清空索引")
            )
            else ""
        )
        return {
            "request_meta": {
                "message_hash": semantic_hash({"message": request.message}),
                "message_length": len(request.message),
                "mode": request.mode,
            },
            "request_policy": "forbidden" if forbidden_code else "allowed",
            "request_policy_code": forbidden_code,
        }

    def authorize_and_load_session(self, state: ChatBIState) -> dict[str, object]:
        request = state["request"]
        if request.session_id is None:
            raise ValueError("orchestrator must assign a session before graph invocation")
        identity = state["identity"]
        session = self.sessions.get_session(identity.subject_id, request.session_id)
        latest_status = None
        if session.latest_answer_id is not None:
            latest_status = self.answers.get_answer(
                identity.subject_id, session.latest_answer_id
            ).status
        decision = self.router.decide(request, session, latest_answer_status=latest_status)
        return {"session_context": session, "turn_decision": decision}

    def retrieve_semantic_candidates(self, state: ChatBIState) -> dict[str, object]:
        candidates = self.retriever.retrieve(state["request"].message)
        candidate_ids = [
            item.item_id
            for items in (
                candidates.dataset_candidates,
                candidates.metric_candidates,
                candidates.field_candidates,
                candidates.recipe_candidates,
                candidates.method_candidates,
                candidates.value_candidates,
            )
            for item in items
        ]
        self.sessions.save_safe_state(
            state["identity"].subject_id,
            state["turn_id"],
            {
                "node": "analyst_planner",
                "semantic_package_version": self.semantic_package_version,
                "candidate_ids": candidate_ids,
            },
        )
        return {"semantic_candidates": candidates}

    async def analyst_planner(self, state: ChatBIState) -> dict[str, object]:
        session = state["session_context"]
        decision = state["turn_decision"]
        active_context = self.router.planner_context(session, decision)
        previous_errors = state.get("validator_error_codes", ())
        if previous_errors:
            attempt = state.get("repair_attempt", 0) + 1
            try:
                repair_decision = self.router.finalize(
                    state["analysis_plan_draft"].turn_relation, session
                )
            except ValueError:
                repair_decision = decision
            draft = await self.planner.repair(
                draft=state["analysis_plan_draft"],
                errors=previous_errors,
                candidates=state["semantic_candidates"],
                turn_decision=repair_decision,
                immutable_question_hash=str(state["request_meta"]["message_hash"]),
                attempt=attempt,
                correlation_id=state["correlation_id"],
                fixture_id=state.get("fixture_id"),
            )
        else:
            attempt = 0
            draft = await self.planner.plan(
                request=state["request"],
                active_context=active_context,
                turn_decision=decision,
                candidates=state["semantic_candidates"],
                current_time=self.now(),
                correlation_id=state["correlation_id"],
                fixture_id=state.get("fixture_id"),
            )
        return {
            "analysis_plan_draft": draft,
            "repair_attempt": attempt,
            "validator_error_codes": (),
        }

    def validate_analysis_plan(self, state: ChatBIState) -> dict[str, object]:
        try:
            decision = self.router.finalize(
                state["analysis_plan_draft"].turn_relation,
                state["session_context"],
            )
            plan, route = self.validator.validate(
                state["analysis_plan_draft"],
                state["semantic_candidates"],
                decision,
            )
            if decision.execution_mode == "reuse" and self._reuse_data_signature_changed(
                state, plan, decision.analytical_base_answer_id
            ):
                decision = self.router.require_requery(decision)
            elif decision.execution_mode == "reuse":
                plan = self._canonical_reuse_plan(
                    state,
                    plan,
                    decision.analytical_base_answer_id,
                )
        except (AnalysisPlanValidationError, ValueError) as error:
            error_code = (
                error.code
                if isinstance(error, AnalysisPlanValidationError)
                else "TURN_RELATION_INVALID"
            )
            if state.get("repair_attempt", 0) < 2:
                return {
                    "analysis_route": "repair",
                    "validator_error_codes": (error_code,),
                }
            plan = self.validator.safe_fallback(
                state["analysis_plan_draft"],
                state["semantic_candidates"],
                state["turn_decision"],
            )
            decision = self.router.finalize(plan.turn_relation, state["session_context"])
            route = "clarify"
        self.sessions.save_turn_decision(state["identity"].subject_id, state["turn_id"], decision)
        self.sessions.save_safe_state(
            state["identity"].subject_id,
            state["turn_id"],
            {
                "node": "validate_analysis_plan",
                "semantic_package_version": self.semantic_package_version,
                "analysis_plan_id": plan.object_id,
                "analysis_plan_hash": plan.content_hash,
            },
        )
        return {
            "analysis_plan": plan,
            "analysis_route": route,
            "turn_decision": decision,
            "validator_error_codes": (),
        }

    def _reuse_data_signature_changed(
        self,
        state: ChatBIState,
        plan: AnalysisPlan,
        base_answer_id: str | None,
    ) -> bool:
        if base_answer_id is None:
            return True
        base = self.answers.get_answer(state["identity"].subject_id, base_answer_id)
        if (
            base.analysis_plan is None
            or base.semantic_package_version != self.semantic_package_version
        ):
            return True
        return self._data_signature(plan) != self._data_signature(base.analysis_plan)

    def _canonical_reuse_plan(
        self,
        state: ChatBIState,
        current: AnalysisPlan,
        base_answer_id: str | None,
    ) -> AnalysisPlan:
        """Keep the validated data tasks immutable while honoring the new turn purpose."""

        if base_answer_id is None:
            raise ValueError("reuse requires an analytical base answer")
        base = self.answers.get_answer(state["identity"].subject_id, base_answer_id)
        if base.analysis_plan is None:
            raise ValueError("reuse base has no analysis plan")
        base_plan = base.analysis_plan
        presentation = (
            current.presentation_preference
            if current.turn_relation.value == "PRESENTATION_CHANGE"
            else base_plan.presentation_preference
        )
        analysis_goal = (
            base_plan.analysis_goal
            if current.turn_relation.value == "PRESENTATION_CHANGE"
            else current.analysis_goal
        )
        payload = {
            "analysis_goal": analysis_goal,
            "question_archetype": base_plan.question_archetype,
            "turn_relation": current.turn_relation,
            "scope": base_plan.scope,
            "metric_decisions": base_plan.metric_decisions,
            "tasks": base_plan.tasks,
            "presentation_preference": presentation,
            "clarification": None,
            "assumptions": tuple(dict.fromkeys([*base_plan.assumptions, *current.assumptions])),
            "limitations": tuple(dict.fromkeys([*base_plan.limitations, *current.limitations])),
            "budget": base_plan.budget,
        }
        return AnalysisPlan(
            object_id=new_id("ap"),
            created_at=self.now(),
            content_hash=semantic_hash(payload),
            provenance=Provenance(
                producer="orchestration.reuse_plan",
                source_ids=(base_plan.object_id, current.object_id),
            ),
            analysis_goal=analysis_goal,
            question_archetype=base_plan.question_archetype,
            turn_relation=current.turn_relation,
            scope=base_plan.scope,
            metric_decisions=base_plan.metric_decisions,
            tasks=base_plan.tasks,
            presentation_preference=presentation,
            clarification=None,
            assumptions=tuple(dict.fromkeys([*base_plan.assumptions, *current.assumptions])),
            limitations=tuple(dict.fromkeys([*base_plan.limitations, *current.limitations])),
            budget=base_plan.budget,
        )

    @staticmethod
    def _data_signature(plan: AnalysisPlan) -> str:
        filters = sorted(
            (
                item.field_id,
                item.operator,
                tuple(str(value) for value in item.values),
            )
            for item in plan.scope.filters
        )
        selected_metrics = sorted(
            item.metric_id for item in plan.metric_decisions if item.decision != "rejected"
        )
        task_shapes = sorted(
            (
                tuple(sorted(task.metric_ids)),
                tuple(sorted(task.dimension_ids)),
                tuple(task.grain),
                tuple(sorted(task.statistical_method_ids)),
            )
            for task in plan.tasks
        )
        return semantic_hash(
            {
                "datasets": sorted(plan.scope.dataset_ids),
                "time_range": plan.scope.time_range.model_dump(mode="json"),
                "filters": filters,
                "metrics": selected_metrics,
                # Per-task shape is required: separate A and B datasets are not
                # interchangeable with one joint A-by-B dataset even though their unions match.
                "task_shapes": task_shapes,
            }
        )

    def resolve_analysis(self, state: ChatBIState) -> dict[str, object]:
        resolved = self.resolver.resolve(state["analysis_plan"])
        return {"resolved_analysis": resolved}

    def persist_terminal(self, state: ChatBIState) -> dict[str, object]:
        plan = state["analysis_plan"]
        is_clarification = plan.clarification is not None
        status = (
            AnswerStatus.CLARIFICATION_REQUIRED if is_clarification else AnswerStatus.UNANSWERABLE
        )
        answer_id = new_id("ans")
        payload = {
            "session_id": state["session_context"].object_id,
            "turn_kind": state["turn_decision"].turn_kind,
            "status": status,
            "semantic_package_version": self.semantic_package_version,
            "analysis_plan_hash": plan.content_hash,
        }
        snapshot = AnswerSnapshot(
            object_id=answer_id,
            created_at=self.now(),
            content_hash=semantic_hash(payload),
            provenance=Provenance(
                producer="orchestration.persist_terminal",
                source_ids=(plan.object_id,),
            ),
            session_id=state["session_context"].object_id,
            chronological_parent_answer_id=state["session_context"].latest_answer_id,
            analytical_base_answer_id=state["turn_decision"].analytical_base_answer_id,
            turn_kind=state["turn_decision"].turn_kind,
            status=status,
            semantic_package_version=self.semantic_package_version,
            metric_versions=tuple(
                item.metric_id for item in plan.metric_decisions if item.decision != "rejected"
            ),
            analysis_plan=plan,
            limitations=plan.limitations,
        )
        self.answers.persist_answer(
            state["identity"].subject_id,
            state["turn_id"],
            snapshot,
            state["session_context"].active_context,
        )
        return {
            "answer_snapshot": snapshot,
            "terminal_status": "CLARIFICATION_REQUIRED" if is_clarification else "UNANSWERABLE",
        }

    def persist_forbidden(self, state: ChatBIState) -> dict[str, object]:
        session = state["session_context"]
        code = state["request_policy_code"]
        answer_id = new_id("ans")
        payload = {
            "session_id": session.object_id,
            "turn_kind": state["turn_decision"].turn_kind,
            "status": AnswerStatus.FORBIDDEN,
            "policy_code": code,
        }
        snapshot = AnswerSnapshot(
            object_id=answer_id,
            created_at=self.now(),
            content_hash=semantic_hash(payload),
            provenance=Provenance(
                producer="orchestration.request_policy",
                source_ids=(str(state["request_meta"]["message_hash"]),),
                metadata={"policy_code": code},
            ),
            session_id=session.object_id,
            chronological_parent_answer_id=session.latest_answer_id,
            analytical_base_answer_id=state["turn_decision"].analytical_base_answer_id,
            turn_kind=state["turn_decision"].turn_kind,
            status=AnswerStatus.FORBIDDEN,
            semantic_package_version=self.semantic_package_version,
            metric_versions=(),
            limitations=("该请求超出只读分析边界。",),
            warnings=(code,),
        )
        self.answers.persist_answer(
            state["identity"].subject_id,
            state["turn_id"],
            snapshot,
            session.active_context,
        )
        self.sessions.save_safe_state(
            state["identity"].subject_id,
            state["turn_id"],
            {
                "node": "persist_forbidden",
                "terminal_status": "COMPLETED",
                "semantic_package_version": self.semantic_package_version,
                "answer_id": answer_id,
            },
        )
        return {"answer_snapshot": snapshot, "terminal_status": "COMPLETED"}

    @staticmethod
    def phase2_ready(state: ChatBIState) -> dict[str, object]:
        resolved = state["resolved_analysis"]
        return {"terminal_status": "PLANNED" if resolved.answerable else "UNANSWERABLE"}

    @staticmethod
    def route_after_resolution(state: ChatBIState) -> str:
        return "ready" if state["resolved_analysis"].answerable else "terminal"
