from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Literal, cast
from uuid import uuid4

from app.agent.contracts import EvidenceBundle, QueryPlan
from app.agent.state import AgentState, RunStatus
from app.api.errors import ReasonCode
from app.api.schemas import (
    ChartData,
    ChatRequest,
    ChatResponse,
    ChatStatus,
    EvidenceResponse,
    KpiItem,
    MetricDefinition,
    TableColumn,
    TableData,
)
from app.config.settings import Settings
from app.gateway.base import OpenSearchGateway
from app.intent.mock_client import MockLLMClient
from app.intent.models import ConversationContext, IntentOutcome, LLMClient
from app.query.dsl import QueryDslBuilder
from app.query.models import CompiledQuery
from app.query.planner import QueryPlanBuilder
from app.query.validator import QueryDslValidator, QueryValidationError
from app.results.models import ProcessedResult, QualityStatus
from app.results.processor import ResultProcessor
from app.semantic.models import CompiledSemanticModel
from app.semantic.resolver import (
    AnswerabilityStatus,
    ResolutionResult,
    SemanticResolver,
)
from app.sessions.models import (
    ChatMessage,
    MessageKind,
    MessageRole,
    PendingClarification,
)
from app.sessions.store import InMemorySessionStore

logger = logging.getLogger(__name__)


class ChatBIAgent:
    """Controlled application service for the complete Mock-first ChatBI flow.

    The LLM-shaped adapter is limited to intent and summary contracts. Field
    resolution, query construction, tool selection, execution, metrics, QA and
    evidence are deterministic program logic.
    """

    _LABELS = {
        "total_count": "记录数量",
        "total_success_count": "成功记录",
        "total_failed_count": "失败记录",
        "other_count": "其他状态",
        "failure_rate": "Failure Rate",
        "channel": "Channel",
        "route": "Route",
        "date": "日期",
        "status": "Status",
        "statusCode": "Status Code",
    }

    def __init__(
        self,
        *,
        settings: Settings,
        model: CompiledSemanticModel,
        gateway: OpenSearchGateway,
        sessions: InMemorySessionStore,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.settings = settings
        self.model = model
        self.gateway = gateway
        self.sessions = sessions
        self.intent = llm_client or MockLLMClient(settings)
        self.resolver = SemanticResolver(model)
        self.planner = QueryPlanBuilder(model)
        self.dsl_builder = QueryDslBuilder(model)
        self.validator = QueryDslValidator(model)
        self.processor = ResultProcessor(model)
        self.blocked_fields = set(model.policy.blocked_fields)

    def answer(self, payload: ChatRequest) -> ChatResponse:
        session = self.sessions.get_or_create(payload.session_id)
        run_id = f"run-{uuid4()}"
        self._append_message(
            session.session_id,
            MessageRole.USER,
            MessageKind.QUESTION,
            payload.message,
            run_id,
        )
        state = AgentState(
            run_id=run_id,
            session_id=session.session_id,
            user_question=payload.message,
            semantic_model_version=self.model.model_version,
        )
        context, effective_question = self._conversation_context(session, payload.message)

        try:
            intent_outcome = self.intent.create_analysis_plan(effective_question, context)
            if intent_outcome.plan is None:
                state = state.transition(RunStatus.NEEDS_CLARIFICATION)
                return self._clarification_reply(
                    state,
                    intent_outcome,
                    original_question=context.original_question or payload.message,
                )

            state = state.transition(RunStatus.PLANNED).model_copy(
                update={"analysis_plan": intent_outcome.plan}, deep=True
            )
            resolution = self.resolver.resolve(intent_outcome.plan)
            if resolution.status is AnswerabilityStatus.NEEDS_CLARIFICATION:
                state = state.transition(RunStatus.NEEDS_CLARIFICATION)
                clarification = IntentOutcome(
                    clarification_question=resolution.clarification_question,
                    clarification_slot=resolution.clarification_slot,
                    clarification_choices=resolution.clarification_choices,
                )
                return self._clarification_reply(
                    state,
                    clarification,
                    original_question=context.original_question or payload.message,
                )
            if resolution.status is AnswerabilityStatus.POLICY_BLOCKED:
                state = state.transition(RunStatus.RESOLVED).transition(RunStatus.POLICY_BLOCKED)
                return self._blocked_reply(state)
            if resolution.status not in {
                AnswerabilityStatus.ANSWERABLE,
                AnswerabilityStatus.ANSWERABLE_WITH_CAVEAT,
            }:
                state = state.transition(RunStatus.RESOLVED).transition(RunStatus.UNSUPPORTED)
                return self._not_answerable_reply(state, resolution)

            state = state.transition(RunStatus.RESOLVED).model_copy(
                update={
                    "field_resolution": resolution.field_resolution,
                    "metric_resolution": resolution.metric_resolution,
                    "answerability": resolution.model_dump(mode="json"),
                    "warnings": [
                        *intent_outcome.warnings,
                        *resolution.caveats,
                        *resolution.reason_codes,
                    ],
                    "metric_versions": resolution.metric_resolution,
                },
                deep=True,
            )
            plans = self.planner.build(
                intent_outcome.plan,
                resolution,
                available_indices=set(self.gateway.list_indices()),
            )
            compiled, validation_evidence = self._compile_and_validate(plans)
            state = state.model_copy(
                update={
                    "query_plans": plans,
                    "compiled_queries": [query.model_dump(mode="json") for query in compiled],
                },
                deep=True,
            ).transition(RunStatus.QUERY_READY)

            execution = self.gateway.execute(compiled)
            state = state.model_copy(
                update={
                    "execution_records": [
                        record.model_dump(mode="json") for record in execution.records
                    ],
                    "raw_results": [result.model_dump(mode="json") for result in execution.results],
                },
                deep=True,
            ).transition(RunStatus.EXECUTED)

            processed = self._process_plans(plans, execution.results)
            primary = processed[0]
            warnings = [
                *state.warnings,
                *primary.warnings,
                *(["ADDITIONAL_QUERY_RESULTS_AVAILABLE"] if len(processed) > 1 else []),
            ]
            if primary.prepared_data.quality.status is QualityStatus.FAILED:
                state = state.transition(RunStatus.QA_FAILED)
                return self._qa_failed_reply(
                    state,
                    plans,
                    compiled,
                    validation_evidence,
                    execution.records,
                    primary,
                    warnings,
                )

            state = state.transition(RunStatus.VALIDATED)
            summary = self.intent.summarize(
                effective_question,
                primary.prepared_data.model_dump(mode="json"),
                warnings,
            )
            if primary.prepared_data.totals.get("total_count") == 0:
                summary = "当前条件下没有数据。"
                primary = primary.model_copy(update={"chart": None}, deep=True)
                warnings.append("NO_DATA")

            evidence = self._build_evidence(
                state,
                plans,
                compiled,
                validation_evidence,
                execution.records,
                primary,
                warnings,
            )
            state = state.model_copy(
                update={
                    "prepared_data": primary.prepared_data.model_dump(mode="json"),
                    "chart_specs": (
                        [primary.chart.model_dump(mode="json")] if primary.chart is not None else []
                    ),
                    "summary": summary,
                    "warnings": self._dedupe(warnings),
                    "evidence": evidence,
                },
                deep=True,
            ).transition(RunStatus.PRESENTED)
            self._save_success(state)
            response = self._answered_reply(state, primary)
            self._append_message(
                session.session_id,
                MessageRole.ASSISTANT,
                MessageKind.ANSWER,
                response.assistant_message,
                run_id,
            )
            return response
        except QueryValidationError as exc:
            return self._safe_error_reply(
                state,
                "查询未通过安全校验，未执行任何数据访问。",
                ReasonCode.QUERY_VALIDATION_FAILED,
                [check.name for check in exc.result.checks if not check.passed],
            )
        except ValueError as exc:
            reason = (
                ReasonCode.INDEX_NOT_AVAILABLE
                if "indices not available" in str(exc)
                else ReasonCode.NOT_ANSWERABLE
            )
            return self._safe_error_reply(
                state,
                "当前 Mock 数据范围无法完成该请求。",
                reason,
                [str(exc)],
                status=ChatStatus.NOT_ANSWERABLE,
            )
        except Exception:
            logger.exception("Unexpected ChatBI execution failure; run_id=%s", state.run_id)
            return self._safe_error_reply(
                state,
                "查询执行失败，请稍后重试或联系维护人员查看服务日志。",
                ReasonCode.EXECUTION_FAILED,
                [],
            )

    def _conversation_context(
        self, session: Any, current_message: str
    ) -> tuple[ConversationContext, str]:
        pending = session.pending_clarification
        if pending is None:
            return (
                ConversationContext(business_timezone=self.settings.business_timezone),
                current_message,
            )
        effective = f"{pending.original_user_question} {current_message}"
        return (
            ConversationContext(
                business_timezone=self.settings.business_timezone,
                pending_question=pending.question,
                pending_missing_slot=pending.missing_slot,
                original_question=pending.original_user_question,
            ),
            effective,
        )

    def _compile_and_validate(
        self, plans: list[QueryPlan]
    ) -> tuple[list[CompiledQuery], list[dict[str, Any]]]:
        compiled: list[CompiledQuery] = []
        validation: list[dict[str, Any]] = []
        for plan in plans:
            for query in self.dsl_builder.build(plan):
                validated, result = self.validator.validate(query)
                compiled.append(validated)
                validation.append(
                    {
                        "query_id": validated.query_id,
                        **result.model_dump(mode="json"),
                    }
                )
        return compiled, validation

    def _process_plans(
        self, plans: list[QueryPlan], raw_results: list[Any]
    ) -> list[ProcessedResult]:
        by_logical: dict[str, list[Any]] = defaultdict(list)
        for raw in raw_results:
            by_logical[raw.logical_query_id].append(raw)
        return [self.processor.process(plan, by_logical.get(plan.query_id, [])) for plan in plans]

    def _clarification_reply(
        self,
        state: AgentState,
        outcome: IntentOutcome,
        *,
        original_question: str,
    ) -> ChatResponse:
        question = outcome.clarification_question or "请补充你希望分析的维度。"
        pending = PendingClarification(
            clarification_id=f"clarification-{uuid4()}",
            question=question,
            missing_slot=outcome.clarification_slot or "unspecified",
            allowed_choices=outcome.clarification_choices,
            partial_analysis_plan=(
                state.analysis_plan.model_dump(mode="json", by_alias=True)
                if state.analysis_plan is not None
                else {}
            ),
            original_user_question=original_question,
        )
        self.sessions.set_pending(state.session_id, pending)
        self._append_message(
            state.session_id,
            MessageRole.ASSISTANT,
            MessageKind.CLARIFICATION,
            question,
            state.run_id,
        )
        return ChatResponse(
            session_id=state.session_id,
            run_id=state.run_id,
            status=ChatStatus.NEEDS_CLARIFICATION,
            assistant_message=question,
            needs_clarification=True,
            clarification_question=question,
            reason_code=ReasonCode.NEEDS_CLARIFICATION,
        )

    def _blocked_reply(self, state: AgentState) -> ChatResponse:
        message = "该请求涉及策略禁止的数据，系统已在后端阻断，未生成或执行查询。"
        self.sessions.set_pending(state.session_id, None)
        self._append_message(
            state.session_id,
            MessageRole.ASSISTANT,
            MessageKind.BLOCKED,
            message,
            state.run_id,
        )
        return ChatResponse(
            session_id=state.session_id,
            run_id=state.run_id,
            status=ChatStatus.BLOCKED,
            assistant_message=message,
            warnings=["POLICY_BLOCKED"],
            reason_code=ReasonCode.POLICY_BLOCKED,
        )

    def _not_answerable_reply(
        self, state: AgentState, resolution: ResolutionResult
    ) -> ChatResponse:
        message = "当前语义模型或允许的查询能力无法可靠回答该问题。"
        self.sessions.set_pending(state.session_id, None)
        self._append_message(
            state.session_id,
            MessageRole.ASSISTANT,
            MessageKind.ERROR,
            message,
            state.run_id,
        )
        return ChatResponse(
            session_id=state.session_id,
            run_id=state.run_id,
            status=ChatStatus.NOT_ANSWERABLE,
            assistant_message=message,
            warnings=resolution.reason_codes,
            reason_code=ReasonCode.NOT_ANSWERABLE,
        )

    def _qa_failed_reply(
        self,
        state: AgentState,
        plans: list[QueryPlan],
        compiled: list[CompiledQuery],
        validation: list[dict[str, Any]],
        execution_records: list[Any],
        processed: ProcessedResult,
        warnings: list[str],
    ) -> ChatResponse:
        message = "查询已完成，但结果未通过数据质量校验，因此不会展示业务结论。"
        evidence = self._build_evidence(
            state,
            plans,
            compiled,
            validation,
            execution_records,
            processed,
            [*warnings, "DATA_QUALITY_FAILED"],
        )
        self.sessions.set_pending(state.session_id, None)
        self._append_message(
            state.session_id,
            MessageRole.ASSISTANT,
            MessageKind.ERROR,
            message,
            state.run_id,
        )
        return ChatResponse(
            session_id=state.session_id,
            run_id=state.run_id,
            status=ChatStatus.ERROR,
            assistant_message=message,
            warnings=self._dedupe([*warnings, "DATA_QUALITY_FAILED"]),
            evidence=self._to_api_evidence(evidence),
            reason_code=ReasonCode.DATA_QUALITY_FAILED,
        )

    def _safe_error_reply(
        self,
        state: AgentState,
        message: str,
        reason: ReasonCode,
        warnings: list[str],
        *,
        status: ChatStatus = ChatStatus.ERROR,
    ) -> ChatResponse:
        self.sessions.set_pending(state.session_id, None)
        self._append_message(
            state.session_id,
            MessageRole.ASSISTANT,
            MessageKind.ERROR,
            message,
            state.run_id,
        )
        return ChatResponse(
            session_id=state.session_id,
            run_id=state.run_id,
            status=status,
            assistant_message=message,
            warnings=self._sanitize_strings(warnings),
            reason_code=reason,
        )

    def _build_evidence(
        self,
        state: AgentState,
        plans: list[QueryPlan],
        compiled: list[CompiledQuery],
        validation: list[dict[str, Any]],
        execution_records: list[Any],
        processed: ProcessedResult,
        warnings: list[str],
    ) -> EvidenceBundle:
        plan = state.analysis_plan
        return EvidenceBundle(
            run_id=state.run_id,
            question=state.user_question,
            semantic_model_version=self.model.model_version,
            analysis_plan=(plan.model_dump(mode="json", by_alias=True) if plan is not None else {}),
            field_resolution=state.field_resolution or {},
            metric_versions=state.metric_versions,
            answerability=state.answerability or {},
            query_plans=[item.model_dump(mode="json") for item in plans],
            compiled_queries=[
                {
                    **item.model_dump(mode="json"),
                    "validation": validation[index],
                }
                for index, item in enumerate(compiled)
            ],
            execution_records=[item.model_dump(mode="json") for item in execution_records],
            prepared_data={
                "totals": processed.prepared_data.totals,
                "row_count": len(processed.prepared_data.rows),
                "raw_result_summary": processed.raw_result_summary,
                "qa": processed.prepared_data.quality.model_dump(mode="json"),
                "provenance": processed.prepared_data.provenance,
            },
            chart_specs=(
                [processed.chart.model_dump(mode="json")] if processed.chart is not None else []
            ),
            warnings=self._dedupe(warnings),
        )

    def _answered_reply(self, state: AgentState, processed: ProcessedResult) -> ChatResponse:
        metric = (
            self.model.metric_map().get("failure_rate")
            if state.metric_versions.get("failure_rate")
            else None
        )
        table = self._table(processed)
        chart = self._chart(processed)
        return ChatResponse(
            session_id=state.session_id,
            run_id=state.run_id,
            status=ChatStatus.ANSWERED,
            assistant_message=state.summary or "分析已完成。",
            kpis=self._kpis(processed.prepared_data.totals),
            table=table,
            chart=chart,
            metric_definition=(
                MetricDefinition(
                    metric_id=metric.metric_id,
                    metric_version=metric.version,
                    status=cast(Literal["POC_DEFINED", "BUSINESS_CONFIRMED"], metric.status),
                )
                if metric is not None
                else None
            ),
            warnings=self._dedupe(state.warnings),
            evidence=(
                self._to_api_evidence(state.evidence) if state.evidence is not None else None
            ),
        )

    def _to_api_evidence(self, evidence: EvidenceBundle) -> EvidenceResponse:
        data = self._sanitize(evidence.model_dump(mode="json"))
        compiled = data.get("compiled_queries", [])
        execution = data.get("execution_records", [])
        tool_names = list(dict.fromkeys(str(record["mcp_tool"]) for record in execution))
        tool_reasons = list(dict.fromkeys(str(record["reason_code"]) for record in execution))
        return EvidenceResponse(
            analysis_plan=data.get("analysis_plan", {}),
            field_resolution=data.get("field_resolution", {}),
            query_plan={
                "plans": data.get("query_plans", []),
                "answerability": data.get("answerability", {}),
            },
            tool=", ".join(tool_names) or None,
            tool_reason_code=", ".join(tool_reasons) or None,
            query_dsl={
                "queries": [
                    {
                        "query_id": item.get("query_id"),
                        "index": item.get("index"),
                        "body": item.get("body", {}),
                        "validation": item.get("validation", {}),
                    }
                    for item in compiled
                ]
            },
            raw_result_summary=data.get("prepared_data", {}),
            chart_data=(
                data.get("chart_specs", [{}])[0].get("data", []) if data.get("chart_specs") else []
            ),
            qa=data.get("prepared_data", {}).get("qa", {}),
        )

    def _save_success(self, state: AgentState) -> None:
        session = self.sessions.get(state.session_id)
        if session is None:
            return
        self.sessions.save(
            session.model_copy(
                update={
                    "pending_clarification": None,
                    "last_analysis_plan": (
                        state.analysis_plan.model_dump(mode="json", by_alias=True)
                        if state.analysis_plan is not None
                        else None
                    ),
                    "last_query_plan": {
                        "plans": [plan.model_dump(mode="json") for plan in state.query_plans]
                    },
                    "last_run_id": state.run_id,
                },
                deep=True,
            )
        )

    def _kpis(self, totals: dict[str, Any]) -> list[KpiItem]:
        order = [
            "total_count",
            "total_success_count",
            "total_failed_count",
            "other_count",
            "failure_rate",
        ]
        items: list[KpiItem] = []
        for key in order:
            if key not in totals:
                continue
            value = totals[key]
            is_percent = key == "failure_rate"
            display = (
                "—"
                if value is None
                else (f"{float(value):.2f}%" if is_percent else f"{int(value):,}")
            )
            items.append(
                KpiItem(
                    id=key,
                    label=self._LABELS.get(key, key),
                    value=value,
                    display_value=display,
                    unit="percent" if is_percent else "records",
                )
            )
        return items

    def _table(self, processed: ProcessedResult) -> TableData | None:
        rows = processed.prepared_data.rows
        if not rows:
            return None
        columns = []
        for item in processed.prepared_data.columns:
            name = item["name"]
            source_type = item["type"]
            column_type = (
                "datetime"
                if source_type == "date"
                else "percent"
                if name == "failure_rate"
                else "number"
                if source_type == "number"
                else "integer"
                if source_type == "integer"
                else "string"
            )
            columns.append(
                TableColumn(
                    field=name,
                    label=self._LABELS.get(name, name),
                    type=column_type,
                )
            )
        return TableData(columns=columns, rows=rows)

    @staticmethod
    def _chart(processed: ProcessedResult) -> ChartData | None:
        if processed.chart is None:
            return None
        return ChartData(
            type=cast(
                Literal["bar", "line", "horizontal_bar", "grouped_bar"],
                processed.chart.type,
            ),
            title=processed.chart.title,
            x_field=processed.chart.x_field,
            y_field=processed.chart.y_field,
            series_field=processed.chart.series_field,
            data=processed.chart.data,
        )

    def _append_message(
        self,
        session_id: str,
        role: MessageRole,
        kind: MessageKind,
        content: str,
        run_id: str,
    ) -> None:
        self.sessions.append_message(
            session_id,
            ChatMessage(
                message_id=f"message-{uuid4()}",
                role=role,
                kind=kind,
                content=content,
                run_id=run_id,
            ),
        )

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: self._sanitize(item)
                for key, item in value.items()
                if key not in self.blocked_fields
            }
        if isinstance(value, list):
            return [self._sanitize(item) for item in value]
        if isinstance(value, str) and value in self.blocked_fields:
            return "[REDACTED]"
        return value

    def _sanitize_strings(self, values: list[str]) -> list[str]:
        return ["[REDACTED]" if value in self.blocked_fields else value for value in values]

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))
