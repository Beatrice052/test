"""Translate actual graph-node completion into safe user progress events."""

# ruff: noqa: RUF001

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from app.contracts.common import JsonValue
from app.contracts.progress import (
    AnalysisProgressEvent,
    AnalysisProgressStage,
    AnalysisProgressStatus,
)
from app.orchestration.state import ChatBIState

type ProgressCallback = Callable[[AnalysisProgressEvent], Awaitable[None]]


class AnalysisProgressReporter:
    """Emit stage facts, not prompts, raw DSL, hidden reasoning, or credentials."""

    def __init__(self, callback: ProgressCallback) -> None:
        self._callback = callback
        self._sequence = 0
        self._completed = False

    async def emit(
        self,
        stage: AnalysisProgressStage,
        status: AnalysisProgressStatus,
        title: str,
        detail: str,
        *,
        safe_summary: dict[str, JsonValue] | None = None,
    ) -> None:
        self._sequence += 1
        await self._callback(
            AnalysisProgressEvent(
                sequence=self._sequence,
                stage=stage,
                status=status,
                title=title,
                detail=detail,
                safe_summary=safe_summary or {},
                occurred_at=datetime.now(UTC),
            )
        )
        if stage == "complete" and status == "completed":
            self._completed = True

    async def started(self) -> None:
        await self.emit(
            "request",
            "running",
            "已接收分析请求",
            "正在校验请求边界、访问权限与会话状态。",
        )

    async def replayed(self) -> None:
        await self.emit(
            "complete",
            "completed",
            "已恢复已有结果",
            "相同请求已完成，本次直接返回已验证的不可变答案。",
            safe_summary={"execution_mode": "idempotent_replay"},
        )

    async def running_elsewhere(self) -> None:
        await self.emit(
            "complete",
            "completed",
            "请求正在处理中",
            "检测到相同请求仍在执行，未启动重复分析。",
            safe_summary={"execution_mode": "deduplicated"},
        )

    async def after_node(self, node: str, state: ChatBIState) -> None:
        handler = getattr(self, f"_after_{node}", None)
        if handler is not None:
            await handler(state)

    async def finish(self, state: ChatBIState) -> None:
        if self._completed:
            return
        terminal = state.get("terminal_status", "COMPLETED")
        await self.emit(
            "complete",
            "completed",
            "分析流程已结束",
            "最终结果已生成，正在加载可视化与证据。",
            safe_summary={"terminal_status": terminal},
        )

    async def _after_validate_request(self, state: ChatBIState) -> None:
        allowed = state.get("request_policy") == "allowed"
        await self.emit(
            "guardrails",
            "completed",
            "请求边界校验完成",
            "请求可进入受控分析流程。" if allowed else "请求触发了安全边界，将返回受控说明。",
            safe_summary={"request_policy": state.get("request_policy", "unknown")},
        )

    async def _after_authorize_and_load_session(self, state: ChatBIState) -> None:
        await self.emit(
            "context",
            "completed",
            "分析上下文已恢复",
            "已加载当前会话和可复用的分析上下文。",
        )
        if state.get("request_policy") == "allowed":
            await self.emit(
                "intent",
                "running",
                "正在理解业务问题",
                "正在检索受控语义候选，并调用 Agent A 识别意图与分析任务。",
            )

    async def _after_retrieve_semantic_candidates(self, state: ChatBIState) -> None:
        candidates = state.get("semantic_candidates")
        if candidates is None:
            return
        count = sum(
            len(items)
            for items in (
                candidates.dataset_candidates,
                candidates.metric_candidates,
                candidates.field_candidates,
                candidates.recipe_candidates,
                candidates.method_candidates,
                candidates.value_candidates,
            )
        )
        await self.emit(
            "intent",
            "running",
            "业务语义候选已就绪",
            "Agent A 正在基于受控候选形成结构化分析方案。",
            safe_summary={"semantic_candidate_count": count},
        )

    async def _after_analyst_planner(self, state: ChatBIState) -> None:
        draft = state.get("analysis_plan_draft")
        if draft is None:
            return
        metrics = [item.metric_id for item in draft.metric_decisions if item.decision != "rejected"]
        dimensions = list(
            dict.fromkeys(dimension for task in draft.tasks for dimension in task.dimension_ids)
        )
        await self.emit(
            "intent",
            "completed",
            "Agent A 已完成意图识别",
            f"识别到用户需要：{draft.analysis_goal[:180]}",
            safe_summary={
                "turn_relation": draft.turn_relation.value,
                "question_archetype": draft.question_archetype,
                "task_count": len(draft.tasks),
                "metric_ids": metrics,
                "dimension_ids": dimensions,
            },
        )

    async def _after_validate_analysis_plan(self, state: ChatBIState) -> None:
        route = state.get("analysis_route")
        if route == "repair":
            await self.emit(
                "intent",
                "running",
                "正在修复分析方案",
                "结构化校验发现不一致，Agent A 将在固定次数内按错误码修复。",
                safe_summary={"repair_attempt": state.get("repair_attempt", 0) + 1},
            )
            return
        if route != "resolve":
            return
        decision = state.get("turn_decision")
        if decision is not None and decision.execution_mode == "reuse":
            await self.emit(
                "dashboard",
                "running",
                "正在调整结果展示",
                "本轮复用已有验证数据，不会重复检索 OpenSearch。",
                safe_summary={"execution_mode": "reuse"},
            )

    async def _after_resolve_analysis(self, state: ChatBIState) -> None:
        resolved = state.get("resolved_analysis")
        if resolved is None:
            return
        await self.emit(
            "query_plan",
            "running",
            "正在规划查询步骤",
            "指标与字段口径已解析。Agent B 正在根据分析任务生成逻辑 QueryPlan，不直接编写 DSL。",
            safe_summary={
                "dataset_ids": list(resolved.dataset_ids),
                "metric_count": len(resolved.metrics),
                "answerable": resolved.answerable,
            },
        )

    async def _after_logical_query_planner(self, state: ChatBIState) -> None:
        draft = state.get("query_plan_draft")
        if draft is None:
            return
        await self.emit(
            "query_plan",
            "completed",
            "Agent B 已生成逻辑 QueryPlan",
            "查询步骤、依赖关系、粒度和结果契约已形成，正在做确定性校验。",
            safe_summary={
                "step_count": len(draft.steps),
                "grains": [list(step.grain) for step in draft.steps],
            },
        )

    async def _after_finalize_query_plan(self, state: ChatBIState) -> None:
        route = state.get("query_route")
        if route == "repair":
            await self.emit(
                "query_plan",
                "running",
                "正在修复逻辑查询计划",
                "确定性校验未通过，Agent B 将按结构化错误码修复计划。",
                safe_summary={"repair_attempt": state.get("query_repair_attempt", 0) + 1},
            )
            return
        if route == "compile":
            plan = state.get("query_plan")
            await self.emit(
                "dsl",
                "running",
                "正在生成受控 OpenSearch DSL",
                "确定性编译器正在把已验证 QueryPlan 转换为 DSL，并执行成本与安全校验。",
                safe_summary={"step_count": 0 if plan is None else len(plan.steps)},
            )

    async def _after_compile_and_validate(self, state: ChatBIState) -> None:
        await self.emit(
            "dsl",
            "completed",
            "OpenSearch DSL 已通过校验",
            "DSL 由受控编译器生成；LLM 无权直接提交或执行原始 DSL。",
            safe_summary={"compiled_query_count": len(state.get("compiled_queries", ()))},
        )
        await self.emit(
            "search",
            "running",
            "正在检索 OpenSearch",
            "正在执行只读查询，并校验超时、分片状态与响应规模。",
        )

    async def _after_execute_and_analyze(self, state: ChatBIState) -> None:
        route = state.get("phase4_route")
        await self.emit(
            "search",
            "completed",
            "OpenSearch 检索已完成",
            "查询响应已转换为受控数据集，并保留可审计执行记录。",
            safe_summary={
                "query_count": len(state.get("execution_records", ())),
                "result_count": len(state.get("raw_results", ())),
            },
        )
        await self.emit(
            "analytics",
            "completed",
            "智能数据分析与质量校验已完成",
            "已完成聚合解析、指标计算、统计特征和数据质量检查。",
            safe_summary={
                "feature_count": len(state.get("feature_summaries", ())),
                "qa_route": route or "unknown",
            },
        )
        if route == "ready":
            await self.emit(
                "dashboard",
                "running",
                "正在生成分析结论与 Dashboard",
                "Agent C 正在提出数据驱动的洞察和图表候选，随后由确定性组件绑定证据。",
            )

    async def _after_produce_answer(self, state: ChatBIState) -> None:
        answer = state.get("answer_snapshot")
        block_count = (
            0
            if answer is None or answer.dashboard_spec is None
            else len(answer.dashboard_spec.blocks)
        )
        await self.emit(
            "dashboard",
            "completed",
            "分析结论与 Dashboard 已验证",
            "关键发现、指标、图表和证据已完成一致性绑定。",
            safe_summary={"dashboard_block_count": block_count},
        )
        await self.finish(state)

    async def _after_reuse_answer(self, state: ChatBIState) -> None:
        await self.emit(
            "dashboard",
            "completed",
            "展示调整已完成",
            "已基于已有验证数据生成新的不可变答案版本。",
            safe_summary={"execution_mode": "reuse"},
        )
        await self.finish(state)

    async def _after_persist_terminal(self, state: ChatBIState) -> None:
        await self.finish(state)

    async def _after_persist_forbidden(self, state: ChatBIState) -> None:
        await self.finish(state)

    async def _after_phase3_failed(self, state: ChatBIState) -> None:
        await self.finish(state)

    async def _after_phase4_qa_failed(self, state: ChatBIState) -> None:
        await self.finish(state)

    async def _after_phase4_gateway_failed(self, state: ChatBIState) -> None:
        await self.finish(state)
