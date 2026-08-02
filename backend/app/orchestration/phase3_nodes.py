"""Agent B and deterministic QueryPlan/DSL nodes."""

from app.agents.logical_query_planner import LogicalQueryPlannerAgent
from app.contracts.error import ErrorDetail, StructuredError
from app.orchestration.state import ChatBIState
from app.persistence.session_repository import SessionRepository
from app.query.compiler import DslCompiler
from app.query.finalizer import QueryPlanFinalizationError, QueryPlanFinalizer
from app.query.validator import CompiledQueryValidator


class Phase3Nodes:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        planner: LogicalQueryPlannerAgent,
        finalizer: QueryPlanFinalizer,
        compiler: DslCompiler,
        validator: CompiledQueryValidator,
        semantic_package_version: str,
    ) -> None:
        self.sessions = sessions
        self.planner = planner
        self.finalizer = finalizer
        self.compiler = compiler
        self.validator = validator
        self.semantic_package_version = semantic_package_version

    async def logical_query_planner(self, state: ChatBIState) -> dict[str, object]:
        self.sessions.save_safe_state(
            state["identity"].subject_id,
            state["turn_id"],
            {
                "node": "logical_query_planner",
                "semantic_package_version": self.semantic_package_version,
                "analysis_plan_id": state["analysis_plan"].object_id,
                "analysis_plan_hash": state["analysis_plan"].content_hash,
            },
        )
        errors = state.get("query_validator_error_codes", ())
        if errors:
            attempt = state.get("query_repair_attempt", 0) + 1
            draft = await self.planner.repair(
                draft=state["query_plan_draft"],
                errors=errors,
                analysis_plan=state["analysis_plan"],
                resolved_analysis=state["resolved_analysis"],
                attempt=attempt,
                correlation_id=state["correlation_id"],
                fixture_id=state.get("fixture_id"),
            )
        else:
            attempt = 0
            draft = await self.planner.plan(
                analysis_plan=state["analysis_plan"],
                resolved_analysis=state["resolved_analysis"],
                correlation_id=state["correlation_id"],
                fixture_id=state.get("fixture_id"),
            )
        return {
            "query_plan_draft": draft,
            "query_repair_attempt": attempt,
            "query_validator_error_codes": (),
        }

    def finalize_query_plan(self, state: ChatBIState) -> dict[str, object]:
        try:
            plan = self.finalizer.finalize(
                state["query_plan_draft"],
                state["analysis_plan"],
                state["resolved_analysis"],
            )
        except QueryPlanFinalizationError as error:
            if state.get("query_repair_attempt", 0) < 2:
                return {
                    "query_route": "repair",
                    "query_validator_error_codes": ("PLAN_QUERY_PLAN_INVALID",),
                }
            structured = StructuredError(
                code="PLAN_QUERY_PLAN_INVALID",
                message="逻辑查询计划未通过确定性校验。",
                correlation_id=state["correlation_id"],
                retryable=False,
                details=(
                    ErrorDetail(
                        code="PLAN_FINALIZER_REJECTED",
                        message=str(error),
                    ),
                ),
                suggested_action="请缩小问题范围或明确分析维度。",
            )
            return {"query_route": "failed", "errors": (structured,)}
        return {
            "query_plan": plan,
            "query_route": "compile",
            "query_validator_error_codes": (),
        }

    def compile_and_validate(self, state: ChatBIState) -> dict[str, object]:
        plan = state["query_plan"]
        compiled = tuple(
            self.compiler.compile(plan, step.step_id)
            for step in plan.steps
            if not step.parameter_bindings
        )
        for query in compiled:
            self.validator.validate(query, plan)
        self.sessions.save_safe_state(
            state["identity"].subject_id,
            state["turn_id"],
            {
                "node": "compile_and_validate",
                "semantic_package_version": self.semantic_package_version,
                "analysis_plan_id": state["analysis_plan"].object_id,
                "analysis_plan_hash": state["analysis_plan"].content_hash,
                "candidate_ids": [query.object_id for query in compiled],
            },
        )
        return {"compiled_queries": compiled}

    @staticmethod
    def phase3_ready(state: ChatBIState) -> dict[str, object]:
        if not state["compiled_queries"]:
            raise ValueError("phase3 cannot complete without a compiled query")
        return {"terminal_status": "COMPILED"}

    @staticmethod
    def phase3_failed(state: ChatBIState) -> dict[str, object]:
        if not state.get("errors"):
            raise ValueError("phase3 failure requires a StructuredError")
        return {"terminal_status": "QUERY_PLAN_FAILED"}
