"""Credential-free local planner for demos; production logic remains validated downstream."""

from __future__ import annotations

import re
from datetime import datetime
from typing import cast
from zoneinfo import ZoneInfo

from app.contracts.analysis import (
    AnalysisBudget,
    AnalysisPlanDraft,
    AnalysisScope,
    AnalyticalTask,
    Clarification,
    FilterIntent,
    GovernedChartType,
    MetricDecision,
    PresentationPreference,
    TurnKind,
)
from app.contracts.common import TimeRange
from app.contracts.dashboard import VisualizationCandidate, VisualizationExplorationDraft
from app.contracts.insight import (
    ClaimBinding,
    ClaimDraft,
    InsightDashboardDraft,
    VisualInsightDraft,
)
from app.contracts.query import ParameterBinding, QueryFilter, QueryPlanDraft, QueryStep
from app.llm.client import ALLOWED_OPERATIONS, OutputModel
from app.llm.mock_chart_preferences import parse_chart_preference


class RuleBasedMockLLMClient:
    """Produce a small, deterministic AnalysisPlanDraft from allowlisted candidate IDs."""

    def __init__(self, *, fail_operations: tuple[str, ...] = ()) -> None:
        self.calls: list[str] = []
        self.input_payloads: list[dict[str, object]] = []
        self.fail_operations = set(fail_operations)

    async def generate(
        self,
        *,
        operation: str,
        system_prompt: str,
        input_payload: dict[str, object],
        output_schema: type[OutputModel],
        timeout_seconds: float,
        correlation_id: str,
    ) -> OutputModel:
        del system_prompt, timeout_seconds, correlation_id
        if operation not in ALLOWED_OPERATIONS:
            raise ValueError(f"operation is not allowed: {operation}")
        self.input_payloads.append(input_payload)
        if operation in self.fail_operations:
            raise RuntimeError(f"injected Mock LLM failure: {operation}")
        if operation == "logical_query_plan" and output_schema is QueryPlanDraft:
            self.calls.append(operation)
            return cast(OutputModel, self._query_plan(input_payload))
        if operation == "json_repair" and output_schema is QueryPlanDraft:
            self.calls.append(operation)
            return cast(OutputModel, self._repair_query_plan(input_payload))
        if operation == "json_repair" and output_schema is InsightDashboardDraft:
            self.calls.append(operation)
            return cast(OutputModel, self._repair_insight_dashboard(input_payload))
        if (
            operation == "post_query_visual_exploration"
            and output_schema is VisualizationExplorationDraft
        ):
            self.calls.append(operation)
            return cast(OutputModel, self._insight_dashboard(input_payload))
        if operation == "post_query_insight_dashboard" and output_schema is InsightDashboardDraft:
            self.calls.append(operation)
            return cast(OutputModel, self._insight_dashboard(input_payload))
        if operation not in {"turn_and_analysis_plan", "json_repair"} or output_schema is not (
            AnalysisPlanDraft
        ):
            raise ValueError("rule-based mock does not support this operation/schema pair")
        self.calls.append(operation)
        draft = (
            self._repair_analysis_plan(input_payload)
            if operation == "json_repair"
            else self._analysis_plan(input_payload)
        )
        return cast(OutputModel, draft)

    @staticmethod
    def _insight_dashboard(
        payload: dict[str, object],
    ) -> InsightDashboardDraft | VisualizationExplorationDraft:
        exploration_stage = payload.get("stage") == "propose_bounded_visual_exploration"
        summaries = payload.get("feature_summaries")
        schemas = payload.get("dataset_schemas")
        if not isinstance(summaries, list) or not summaries or not isinstance(schemas, list):
            if exploration_stage:
                return VisualizationExplorationDraft(
                    limitations=("缺少已验证的数据特征摘要",),
                )
            return InsightDashboardDraft(
                answer_summary="没有可用于分析的已验证数据摘要。",
                fallback_requested=True,
                limitations=("缺少已验证的数据特征摘要",),
            )
        schema_items = [item for item in schemas if isinstance(item, dict)]
        summary_by_dataset = {
            str(item.get("dataset_id")): item for item in summaries if isinstance(item, dict)
        }
        raw_metric_definitions = payload.get("metric_definitions", ())
        metric_items = raw_metric_definitions if isinstance(raw_metric_definitions, list) else []
        metric_definitions = {
            f"{item.get('metric_id')}.{item.get('version')}": item
            for item in metric_items
            if isinstance(item, dict)
            and isinstance(item.get("metric_id"), str)
            and isinstance(item.get("version"), str)
        }
        raw_analysis_plan = payload.get("analysis_plan")
        analysis_plan = raw_analysis_plan if isinstance(raw_analysis_plan, dict) else {}
        raw_tasks = analysis_plan.get("tasks", ())
        tasks = (
            tuple(item for item in raw_tasks if isinstance(item, dict))
            if isinstance(raw_tasks, list)
            else ()
        )
        required_task_ids = tuple(
            str(item["task_id"])
            for item in tasks
            if item.get("priority") == "required" and isinstance(item.get("task_id"), str)
        )
        requested_intents = tuple(
            dict.fromkeys(
                str(intent)
                for task in tasks
                for intent in (
                    task.get("visualization_intents", ())
                    if isinstance(task.get("visualization_intents"), list)
                    else ()
                )
            )
        )
        analysis_types = {
            str(item.get("analysis_type", "")) for item in tasks if item.get("analysis_type")
        }

        def task_ids_for_intents(*intents: str) -> tuple[str, ...]:
            requested = set(intents)
            matched = tuple(
                str(task["task_id"])
                for task in tasks
                if isinstance(task.get("task_id"), str)
                and isinstance(task.get("visualization_intents"), list)
                and requested.intersection(
                    str(item) for item in task.get("visualization_intents", ())
                )
            )
            return matched or required_task_ids

        def wants(intent: str) -> bool:
            return not requested_intents or intent in requested_intents

        def grain(schema: dict[str, object]) -> tuple[str, ...]:
            raw = schema.get("grain", ())
            return tuple(str(item) for item in raw) if isinstance(raw, list) else ()

        def column_names(schema: dict[str, object]) -> tuple[str, ...]:
            raw = schema.get("columns", ())
            if not isinstance(raw, list):
                return ()
            return tuple(
                str(item["name"]) for item in raw if isinstance(item, dict) and "name" in item
            )

        def columns(schema: dict[str, object]) -> tuple[dict[str, object], ...]:
            raw = schema.get("columns", ())
            return (
                tuple(item for item in raw if isinstance(item, dict))
                if isinstance(raw, list)
                else ()
            )

        def dimension_column(schema: dict[str, object], field_id: str) -> dict[str, object] | None:
            return next(
                (
                    item
                    for item in columns(schema)
                    if item.get("name") == field_id and item.get("semantic_role") == "dimension"
                ),
                None,
            )

        def is_time(schema: dict[str, object], field_id: str) -> bool:
            item = dimension_column(schema, field_id)
            return item is not None and (
                item.get("semantic_type") == "time_dimension" or item.get("data_type") == "datetime"
            )

        def is_status(schema: dict[str, object], field_id: str) -> bool:
            item = dimension_column(schema, field_id)
            if item is None:
                return False
            leaf = str(item.get("name", "")).rsplit(".", 1)[-1].casefold()
            display = str(item.get("display_name", "")).casefold()
            return leaf == "status" or display in {"status", "状态"}

        def is_category(schema: dict[str, object], field_id: str) -> bool:
            item = dimension_column(schema, field_id)
            return item is not None and (
                item.get("semantic_type") == "categorical_dimension"
                or (
                    item.get("semantic_type") is None
                    and item.get("semantic_role") == "dimension"
                    and item.get("data_type") != "datetime"
                )
            )

        def display_name(schema: dict[str, object], field_id: str) -> str:
            item = dimension_column(schema, field_id)
            if is_status(schema, field_id):
                return "状态"
            value = item.get("display_name") if item is not None else None
            return str(value) if isinstance(value, str) and value else "类别"

        def has_rows(schema: dict[str, object]) -> bool:
            return (
                int(summary_by_dataset.get(str(schema.get("dataset_id")), {}).get("row_count", 0))
                > 0
            )

        def metric_columns(schema: dict[str, object]) -> tuple[dict[str, object], ...]:
            return tuple(
                item
                for item in columns(schema)
                if item.get("semantic_role") == "metric"
                and not ("record_count" in column_names(schema) and item.get("unit") == "count")
            )

        def metric_label(column: dict[str, object]) -> str:
            definition = metric_definitions.get(str(column.get("name")), {})
            label = definition.get("display_name")
            if isinstance(label, str) and label:
                return label
            return str(column.get("metric_id") or column.get("name") or "指标")

        def find_schema(*, exact_grain: tuple[str, ...] | None = None) -> dict[str, object] | None:
            return next(
                (
                    item
                    for item in schema_items
                    if (exact_grain is None or grain(item) == exact_grain) and has_rows(item)
                ),
                None,
            )

        overall = find_schema(exact_grain=())
        category = next(
            (
                item
                for item in schema_items
                if len(grain(item)) == 1
                and is_category(item, grain(item)[0])
                and not is_status(item, grain(item)[0])
                and has_rows(item)
            ),
            None,
        )
        time_only = next(
            (
                item
                for item in schema_items
                if len(grain(item)) == 1 and is_time(item, grain(item)[0]) and has_rows(item)
            ),
            None,
        )
        time_category = next(
            (
                item
                for item in schema_items
                if len(grain(item)) == 2
                and any(is_time(item, name) for name in grain(item))
                and any(
                    is_category(item, name) and not is_status(item, name) for name in grain(item)
                )
                and has_rows(item)
            ),
            None,
        )
        category_composition = next(
            (
                item
                for item in schema_items
                if len(grain(item)) == 2
                and any(is_status(item, name) for name in grain(item))
                and any(
                    is_category(item, name) and not is_status(item, name) for name in grain(item)
                )
                and has_rows(item)
            ),
            None,
        )
        primary = overall or category or time_only or time_category or schema_items[0]
        primary_id = str(primary.get("dataset_id", ""))
        primary_summary = summary_by_dataset.get(primary_id, {})
        if int(primary_summary.get("row_count", 0)) == 0:
            if exploration_stage:
                return VisualizationExplorationDraft(limitations=("已验证结果为空",))
            return InsightDashboardDraft(
                answer_summary="所选分析范围没有匹配的消息记录。",
                fallback_requested=True,
                limitations=("已验证结果为空",),
            )

        claims: list[ClaimDraft] = []
        if overall is not None and "record_count" in column_names(overall):
            overall_id = str(overall["dataset_id"])
            claims.append(
                ClaimDraft(
                    claim_id="claim_overall_record_count",
                    claim_type="value",
                    template="所选时间范围内共记录 {value} 条消息。",
                    importance="primary",
                    bindings=(
                        ClaimBinding(
                            name="value",
                            dataset_id=overall_id,
                            selector="first",
                            column="record_count",
                        ),
                    ),
                )
            )
            for metric_column in metric_columns(overall):
                metric_name = str(metric_column.get("name", ""))
                if not metric_name:
                    continue
                label = metric_label(metric_column)
                claims.append(
                    ClaimDraft(
                        claim_id=f"claim_overall_{metric_name}",
                        claim_type="value",
                        template=f"按已确认口径计算, 整体{label}为 {{metric_value}}。",
                        importance="primary",
                        bindings=(
                            ClaimBinding(
                                name="metric_value",
                                dataset_id=overall_id,
                                selector="first",
                                column=metric_name,
                            ),
                        ),
                    )
                )
        if category is not None and "record_count" in column_names(category):
            category_id = str(category["dataset_id"])
            category_field = grain(category)[0]
            category_label = display_name(category, category_field)
            claims.append(
                ClaimDraft(
                    claim_id="claim_category_record_count_rank",
                    claim_type="ranking",
                    template=(
                        f"{category_label} 中 {{category}} 的消息记录数最高, 为 {{value}} 条。"
                    ),
                    importance="primary",
                    bindings=(
                        ClaimBinding(
                            name="category",
                            dataset_id=category_id,
                            selector="argmax:record_count",
                            column=category_field,
                        ),
                        ClaimBinding(
                            name="value",
                            dataset_id=category_id,
                            selector="argmax:record_count",
                            column="record_count",
                        ),
                    ),
                )
            )
            for metric_column in metric_columns(category):
                metric_name = str(metric_column.get("name", ""))
                if not metric_name:
                    continue
                label = metric_label(metric_column)
                claims.append(
                    ClaimDraft(
                        claim_id=f"claim_category_{metric_name}_rank",
                        claim_type="ranking",
                        template=(
                            f"{category_label} 中 {{category}} 的{label}最高, "
                            "为 {metric_value}; 需结合分母与样本质量判断。"
                        ),
                        importance="secondary",
                        bindings=(
                            ClaimBinding(
                                name="category",
                                dataset_id=category_id,
                                selector=f"argmax:{metric_name}",
                                column=category_field,
                            ),
                            ClaimBinding(
                                name="metric_value",
                                dataset_id=category_id,
                                selector=f"argmax:{metric_name}",
                                column=metric_name,
                            ),
                        ),
                    )
                )
        if time_only is not None and "record_count" in column_names(time_only):
            time_id = str(time_only["dataset_id"])
            time_field = grain(time_only)[0]
            claims.append(
                ClaimDraft(
                    claim_id="claim_time_peak",
                    claim_type="trend",
                    template="{period} 的消息记录数为期间峰值, 共 {value} 条。",
                    importance="secondary",
                    bindings=(
                        ClaimBinding(
                            name="period",
                            dataset_id=time_id,
                            selector="argmax:record_count",
                            column=time_field,
                        ),
                        ClaimBinding(
                            name="value",
                            dataset_id=time_id,
                            selector="argmax:record_count",
                            column="record_count",
                        ),
                    ),
                )
            )
        if time_category is not None and "record_count" in column_names(time_category):
            time_category_id = str(time_category["dataset_id"])
            time_field = next(item for item in grain(time_category) if is_time(time_category, item))
            category_field = next(
                item
                for item in grain(time_category)
                if is_category(time_category, item) and not is_status(time_category, item)
            )
            claims.append(
                ClaimDraft(
                    claim_id="claim_time_category_peak",
                    claim_type="trend",
                    template="{period} 的 {category} 消息量为分组趋势峰值, 共 {value} 条。",
                    importance="secondary",
                    bindings=(
                        ClaimBinding(
                            name="period",
                            dataset_id=time_category_id,
                            selector="argmax:record_count",
                            column=time_field,
                        ),
                        ClaimBinding(
                            name="category",
                            dataset_id=time_category_id,
                            selector="argmax:record_count",
                            column=category_field,
                        ),
                        ClaimBinding(
                            name="value",
                            dataset_id=time_category_id,
                            selector="argmax:record_count",
                            column="record_count",
                        ),
                    ),
                )
            )
        if category_composition is not None and "record_count" in column_names(
            category_composition
        ):
            composition_id = str(category_composition["dataset_id"])
            status_field = next(
                item
                for item in grain(category_composition)
                if is_status(category_composition, item)
            )
            category_field = next(
                item for item in grain(category_composition) if item != status_field
            )
            claims.append(
                ClaimDraft(
                    claim_id="claim_category_composition_peak",
                    claim_type="comparison",
                    template="{category} 的 {status} 组合消息量最高, 共 {value} 条。",
                    importance="secondary",
                    bindings=(
                        ClaimBinding(
                            name="category",
                            dataset_id=composition_id,
                            selector="argmax:record_count",
                            column=category_field,
                        ),
                        ClaimBinding(
                            name="status",
                            dataset_id=composition_id,
                            selector="argmax:record_count",
                            column=status_field,
                        ),
                        ClaimBinding(
                            name="value",
                            dataset_id=composition_id,
                            selector="argmax:record_count",
                            column="record_count",
                        ),
                    ),
                )
            )

        visualizations: list[VisualizationCandidate] = []
        time_row_count = (
            int(summary_by_dataset.get(str(time_only["dataset_id"]), {}).get("row_count", 0))
            if time_only is not None
            else 0
        )
        time_category_row_count = (
            int(summary_by_dataset.get(str(time_category["dataset_id"]), {}).get("row_count", 0))
            if time_category is not None
            else 0
        )
        series_count = (
            max(1, time_category_row_count // max(1, time_row_count))
            if time_category is not None and time_row_count >= 2
            else 0
        )
        time_intent = "anomaly" if "anomaly" in analysis_types else "time_trend"
        wants_time = wants(time_intent) or (time_intent == "anomaly" and wants("time_trend"))
        # One analytical question gets one default chart. A readable multi-series view
        # subsumes the aggregate trend; otherwise use the single-series rollup.
        if wants_time and time_category is not None and 1 < series_count <= 8:
            time_field = next(item for item in grain(time_category) if is_time(time_category, item))
            category_field = next(
                item
                for item in grain(time_category)
                if is_category(time_category, item) and not is_status(time_category, item)
            )
            category_label = display_name(time_category, category_field)
            visualizations.append(
                VisualizationCandidate(
                    candidate_id="vc_category_time_trend",
                    analytical_question=(
                        f"各{category_label}异常筛查"
                        if time_intent == "anomaly"
                        else f"各{category_label}分期消息量趋势"
                    ),
                    intent=time_intent,
                    preferred_chart_types=("line",),
                    dataset_id=str(time_category["dataset_id"]),
                    task_ids=task_ids_for_intents("time_trend", "anomaly"),
                    dimension_roles={"time": time_field, "series": category_field},
                    measure_roles={"value": "record_count"},
                    priority="required",
                    reason=(
                        "按已注册统计方法标记异常候选, 不将统计异常直接称为业务故障。"
                        if time_intent == "anomaly"
                        else f"比较各{category_label}随时间的变化, 识别增长、回落和结构变化。"
                    ),
                )
            )
        elif wants_time and time_only is not None and time_row_count >= 2:
            visualizations.append(
                VisualizationCandidate(
                    candidate_id="vc_total_time_trend",
                    analytical_question=(
                        "消息量异常筛查" if time_intent == "anomaly" else "消息量趋势"
                    ),
                    intent=time_intent,
                    preferred_chart_types=("line",) if time_row_count >= 4 else ("bar", "line"),
                    dataset_id=str(time_only["dataset_id"]),
                    task_ids=task_ids_for_intents("time_trend", "anomaly"),
                    dimension_roles={"time": grain(time_only)[0]},
                    measure_roles={"value": "record_count"},
                    priority="required",
                    reason=(
                        "按已注册统计方法标记异常候选, 不将统计异常直接称为业务故障。"
                        if time_intent == "anomaly"
                        else "观察各期规模变化与峰值, 回答所选时间范围的走势。"
                    ),
                )
            )
        comparison_intent = "pareto" if "pareto" in analysis_types else "ranked_comparison"
        if category is not None and (wants(comparison_intent) or wants("ranked_comparison")):
            category_field = grain(category)[0]
            category_label = display_name(category, category_field)
            visualizations.append(
                VisualizationCandidate(
                    candidate_id="vc_category_ranking",
                    analytical_question=(
                        f"{category_label}累计贡献"
                        if comparison_intent == "pareto"
                        else f"{category_label}消息量排名"
                    ),
                    intent=comparison_intent,
                    preferred_chart_types=(
                        ("pareto", "bar") if comparison_intent == "pareto" else ("bar", "dot")
                    ),
                    dataset_id=str(category["dataset_id"]),
                    task_ids=task_ids_for_intents("ranked_comparison", "pareto"),
                    dimension_roles={"category": category_field},
                    measure_roles={"value": "record_count"},
                    priority="required",
                    reason=(
                        f"同时查看{category_label}贡献值与累计占比, 识别主要原因集合。"
                        if comparison_intent == "pareto"
                        else f"比较{category_label}规模与贡献集中度, 识别主要承载类别。"
                    ),
                )
            )
        if category_composition is not None and wants("composition"):
            status_field = next(
                item
                for item in grain(category_composition)
                if is_status(category_composition, item)
            )
            category_field = next(
                item for item in grain(category_composition) if item != status_field
            )
            category_label = display_name(category_composition, category_field)
            status_label = display_name(category_composition, status_field)
            visualizations.append(
                VisualizationCandidate(
                    candidate_id="vc_category_composition",
                    analytical_question=f"各{category_label}{status_label}构成",
                    intent="composition",
                    preferred_chart_types=("stacked_bar",),
                    dataset_id=str(category_composition["dataset_id"]),
                    task_ids=task_ids_for_intents("composition"),
                    dimension_roles={"category": category_field, "series": status_field},
                    measure_roles={"value": "record_count"},
                    priority="recommended",
                    reason=f"解释每个{category_label}在{status_label}维度上的结构与差异。",
                )
            )
        if exploration_stage:
            return VisualizationExplorationDraft(candidates=tuple(visualizations))

        def claim_task_ids(claim: ClaimDraft) -> tuple[str, ...]:
            if claim.claim_id.startswith("claim_category_composition"):
                return task_ids_for_intents("composition")
            if claim.claim_id.startswith("claim_time"):
                return task_ids_for_intents("time_trend", "anomaly")
            if claim.claim_id.startswith("claim_category"):
                return task_ids_for_intents("ranked_comparison", "pareto")
            return required_task_ids

        prepared_claims = tuple(
            item.model_copy(update={"task_ids": claim_task_ids(item)}) for item in claims
        )
        raw_previews = payload.get("visualization_previews", ())
        preview_items = (
            tuple(item for item in raw_previews if isinstance(item, dict))
            if isinstance(raw_previews, list)
            else ()
        )
        visual_insights: list[VisualInsightDraft] = []
        for preview in preview_items:
            if preview.get("decision") not in {
                "ACCEPT",
                "ACCEPT_WITH_TRANSFORM",
                "DOWNGRADE_TO_TABLE",
            }:
                continue
            preview_id = preview.get("object_id")
            dataset_id = preview.get("dataset_id")
            if not isinstance(preview_id, str) or not isinstance(dataset_id, str):
                continue
            encoding_raw = preview.get("encoding")
            encoding = encoding_raw if isinstance(encoding_raw, dict) else {}
            measure_columns = {
                str(item)
                for item in (encoding.get("value"), encoding.get("y"))
                if isinstance(item, str)
            }
            matching_claim_ids = tuple(
                claim.claim_id
                for claim in prepared_claims
                if claim.bindings
                and all(binding.dataset_id == dataset_id for binding in claim.bindings)
                and (
                    not measure_columns
                    or any(binding.column in measure_columns for binding in claim.bindings)
                )
            )
            if not matching_claim_ids:
                continue
            purpose = preview.get("purpose")
            visual_insights.append(
                VisualInsightDraft(
                    insight_id=f"insight_{len(visual_insights) + 1}",
                    preview_id=preview_id,
                    claim_ids=matching_claim_ids[:3],
                    purpose=str(purpose)
                    if isinstance(purpose, str)
                    else "解释当前图表中的主要差异。",
                )
            )
        return InsightDashboardDraft(
            answer_summary="已根据问题中实际选择的指标、维度与粒度完成受治理分析。",
            claims=prepared_claims,
            visual_insights=tuple(visual_insights),
            limitations=("消息量按记录数统计, 不自动等同于去重发送量。",),
            follow_up_suggestions=(
                "下钻质量指标较高类别的明细原因",
                "切换到更细时间粒度查看峰值和探索性异常",
                "按当前主要维度筛选后继续分析构成",
            ),
        )

    @staticmethod
    def _query_plan(payload: dict[str, object]) -> QueryPlanDraft:
        analysis = payload.get("analysis_plan")
        resolved = payload.get("resolved")
        budgets = payload.get("budgets")
        if not isinstance(analysis, dict) or not isinstance(resolved, dict):
            raise ValueError("logical query payload is incomplete")
        tasks = analysis.get("tasks", ())
        if not isinstance(tasks, list):
            tasks = []
        metrics = resolved.get("metrics", ())
        if not isinstance(metrics, list):
            metrics = []
        executable_metrics = [
            f"{item['metric_id']}.{item['version']}"
            for item in metrics
            if isinstance(item, dict) and item.get("executable") is True
        ]
        required_fields = [
            str(field_id)
            for item in metrics
            if isinstance(item, dict) and item.get("executable") is True
            for field_id in item.get("required_field_ids", ())
        ]
        task_dimensions = [
            str(field_id)
            for task in tasks
            if isinstance(task, dict)
            for field_id in task.get("dimension_ids", ())
        ]
        task_grain = [
            str(grain)
            for task in tasks
            if isinstance(task, dict)
            for grain in task.get("grain", ())
        ]
        time_field_id = str(resolved["time_field_id"])
        dimensions = list(dict.fromkeys([*task_dimensions, *required_fields]))
        if any(item in {"day", "week", "month"} for item in task_grain):
            dimensions = [item for item in dimensions if item != time_field_id]
            dimensions.insert(0, time_field_id)
        filters_raw = resolved.get("filters", ())
        filters = tuple(
            QueryFilter(
                field_id=str(item["field_id"]),
                operator=str(item["operator"]),  # type: ignore[arg-type]
                values=tuple(item.get("values", ())),
            )
            for item in filters_raw
            if isinstance(item, dict)
        )
        dataset_ids = tuple(str(item) for item in resolved.get("dataset_ids", ()))
        if not dataset_ids:
            raise ValueError("resolved analysis has no dataset")
        max_buckets = int(budgets.get("max_buckets", 5000)) if isinstance(budgets, dict) else 5000
        estimate = min(max_buckets, max(1, 20 ** max(1, len(dimensions))))
        step = QueryStep(
            step_id="q1_base",
            purpose_task_ids=tuple(
                str(task["task_id"]) for task in tasks if isinstance(task, dict)
            ),
            dataset_id=dataset_ids[0],
            index_patterns=tuple(str(item) for item in resolved.get("index_route_candidates", ())),
            time_range=TimeRange.model_validate(resolved["time_range"], strict=False),
            time_field_id=time_field_id,
            filters=filters,
            dimensions=tuple(dimensions),
            measures=tuple(executable_metrics),
            grain=tuple(
                dict.fromkeys(task_grain or [field.rsplit(".", 1)[-1] for field in dimensions])
            ),
            result_contract_id="dc_q1_base",
            estimated_buckets=estimate,
        )
        questions = " ".join(
            str(task.get("analytical_question", "")) for task in tasks if isinstance(task, dict)
        )
        category_field = next(
            (item for item in task_dimensions if item != time_field_id and item in dimensions),
            None,
        )
        if "TOP 3" in questions.upper() and category_field is not None:
            category_leaf = category_field.rsplit(".", 1)[-1]
            q1 = step.model_copy(
                update={
                    "step_id": "q1_top_categories",
                    "dimensions": (category_field,),
                    "grain": (category_leaf,),
                    "result_contract_id": "dc_q1_top_categories",
                    "estimated_buckets": 20,
                }
            )
            q2 = step.model_copy(
                update={
                    "step_id": "q2_time_top_categories",
                    "dimensions": (time_field_id, category_field),
                    "grain": (task_grain[0] if task_grain else "time", category_leaf),
                    "result_contract_id": "dc_q2_time_top_categories",
                    "depends_on": (q1.step_id,),
                    "parameter_bindings": (
                        ParameterBinding(
                            parameter=f"{category_leaf}_values",
                            source_dataset_contract=q1.result_contract_id,
                            selection="top_n",
                            metric_id="record_count",
                            n=3,
                        ),
                    ),
                    "estimated_buckets": min(max_buckets - 20, 400),
                }
            )
            return QueryPlanDraft(
                analysis_plan_id=str(resolved["analysis_plan_id"]),
                steps=(q1, q2),
                consolidation_notes=("two-stage Top N dependency",),
            )
        return QueryPlanDraft(
            analysis_plan_id=str(resolved["analysis_plan_id"]),
            steps=(step,),
            consolidation_notes=("compatible tasks consolidated into q1_base",),
        )

    @staticmethod
    def _repair_query_plan(payload: dict[str, object]) -> QueryPlanDraft:
        raw = payload.get("original_output")
        allowed = payload.get("allowed_ids")
        if not isinstance(raw, dict) or not isinstance(allowed, dict):
            raise ValueError("query repair payload is incomplete")
        draft = QueryPlanDraft.model_validate(raw, strict=False)
        datasets = tuple(str(item) for item in allowed.get("dataset", ()))
        fields = set(str(item) for item in allowed.get("field", ()))
        metrics = set(str(item) for item in allowed.get("metric", ()))
        indices = set(str(item) for item in allowed.get("index", ()))
        known_steps: set[str] = set()
        repaired_steps: list[QueryStep] = []
        for step in draft.steps:
            dataset_id = step.dataset_id if step.dataset_id in datasets else datasets[0]
            repaired = step.model_copy(
                update={
                    "dataset_id": dataset_id,
                    "index_patterns": tuple(
                        item for item in step.index_patterns if item in indices
                    ),
                    "time_range": TimeRange.model_validate(
                        payload["authoritative_time_range"], strict=False
                    ),
                    "time_field_id": str(payload["authoritative_time_field_id"]),
                    "filters": tuple(item for item in step.filters if item.field_id in fields),
                    "dimensions": tuple(item for item in step.dimensions if item in fields),
                    "measures": tuple(item for item in step.measures if item in metrics),
                    "depends_on": tuple(item for item in step.depends_on if item in known_steps),
                }
            )
            repaired_steps.append(repaired)
            known_steps.add(repaired.step_id)
        return draft.model_copy(
            update={
                "analysis_plan_id": str(payload["authoritative_analysis_plan_id"]),
                "steps": tuple(repaired_steps),
            }
        )

    @staticmethod
    def _repair_insight_dashboard(payload: dict[str, object]) -> InsightDashboardDraft:
        raw = payload.get("original_output")
        errors = payload.get("validator_error_codes")
        if not isinstance(raw, dict) or not isinstance(errors, list):
            raise ValueError("insight repair payload is incomplete")
        draft = InsightDashboardDraft.model_validate(raw, strict=False)
        allowed = payload.get("allowed_ids")
        rejected_indices: set[int] = set()
        for error in errors:
            if not isinstance(error, str):
                continue
            prefix = error.split(":", 1)[0]
            if prefix.isdigit():
                rejected_indices.add(int(prefix))
        required_task_ids = (
            tuple(str(item) for item in allowed.get("required_task", ()))
            if isinstance(allowed, dict)
            else ()
        )
        claims = tuple(
            item for index, item in enumerate(draft.claims) if index not in rejected_indices
        )
        claims = tuple(item.model_copy(update={"task_ids": required_task_ids}) for item in claims)
        allowed_preview_ids = (
            set(str(item) for item in allowed.get("preview", ()))
            if isinstance(allowed, dict)
            else set()
        )
        retained_claim_ids = {item.claim_id for item in claims}
        visual_insights = tuple(
            item
            for item in draft.visual_insights
            if item.preview_id in allowed_preview_ids
            and set(item.claim_ids).issubset(retained_claim_ids)
        )
        return draft.model_copy(
            update={
                "claims": claims,
                "visual_insights": visual_insights,
                "fallback_requested": not claims,
                "limitations": tuple(
                    dict.fromkeys([*draft.limitations, "invalid claims removed during Mock repair"])
                ),
            }
        )

    @staticmethod
    def _repair_analysis_plan(payload: dict[str, object]) -> AnalysisPlanDraft:
        raw = payload.get("original_output")
        allowed = payload.get("allowed_ids")
        if not isinstance(raw, dict) or not isinstance(allowed, dict):
            raise ValueError("repair payload is missing original_output or allowed_ids")
        draft = AnalysisPlanDraft.model_validate(raw, strict=False)
        allowed_datasets = set(str(item) for item in allowed.get("dataset", ()))
        allowed_metrics = set(str(item) for item in allowed.get("metric", ()))
        allowed_fields = set(str(item) for item in allowed.get("field", ()))
        allowed_methods = set(str(item) for item in allowed.get("method", ()))
        filters = tuple(item for item in draft.scope.filters if item.field_id in allowed_fields)
        datasets = tuple(item for item in draft.scope.dataset_ids if item in allowed_datasets)
        if not datasets and allowed_datasets:
            datasets = (sorted(allowed_datasets)[0],)
        scope = draft.scope.model_copy(update={"dataset_ids": datasets, "filters": filters})
        decisions = tuple(
            item for item in draft.metric_decisions if item.metric_id in allowed_metrics
        )
        tasks = tuple(
            task.model_copy(
                update={
                    "metric_ids": tuple(
                        item for item in task.metric_ids if item in allowed_metrics
                    ),
                    "dimension_ids": tuple(
                        item for item in task.dimension_ids if item in allowed_fields
                    ),
                    "statistical_method_ids": tuple(
                        item for item in task.statistical_method_ids if item in allowed_methods
                    ),
                }
            )
            for task in draft.tasks
        )
        return draft.model_copy(
            update={
                "turn_relation": TurnKind(str(payload["authoritative_turn_kind"])),
                "scope": scope,
                "metric_decisions": decisions,
                "tasks": tasks,
            }
        )

    def _analysis_plan(self, payload: dict[str, object]) -> AnalysisPlanDraft:
        message = str(payload["user_message"])
        datasets = self._candidate_ids(payload, "candidate_datasets")
        metric_items = self._candidate_items(payload, "candidate_metrics")
        field_items = self._candidate_items(payload, "candidate_fields")
        metrics = tuple(str(item["item_id"]) for item in metric_items)
        fields = tuple(str(item["item_id"]) for item in field_items)
        methods = self._candidate_ids(payload, "candidate_methods")
        relation = self._mock_turn_kind(message, payload)
        chart_preference = parse_chart_preference(message)
        time_range = self._time_range(message, payload)
        active_context = payload.get("session_active_context")
        reuse_relations = {TurnKind.PRESENTATION_CHANGE, TurnKind.EXPLANATION}

        selected_metric = self._select_metric(message, metric_items)
        explicitly_selected_metrics = tuple(
            str(item["item_id"]) for item in metric_items if self._field_matches(message, item)
        )
        operational_overview = any(
            token in message for token in ("发送情况", "消息情况", "运行情况", "运营情况")
        )
        time_requested = bool(
            re.search(
                r"(?:(?:20\d{2})年)?(?:1[0-2]|[1-9])月\s*(?:至|到|[-~—])\s*"
                r"(?:(?:20\d{2})年)?(?:1[0-2]|[1-9])月",
                message,
            )
        ) or any(
            word in message
            for word in (
                "每天",
                "每周",
                "每月",
                "趋势",
                "异常",
                "5、6、7月",
                "异常日期",
                "最近三个月",
                "近三个月",
                "过去三个月",
            )
        )
        if relation in {
            TurnKind.FILTER_CHANGE,
            TurnKind.TIME_CHANGE,
            *reuse_relations,
        } and isinstance(active_context, dict):
            active_metrics = active_context.get("metric_ids", ())
            if isinstance(active_metrics, list):
                selected_metric = next(
                    (str(item) for item in active_metrics if str(item) in metrics),
                    selected_metric,
                )
        selected_dimensions = self._select_dimensions(
            message,
            field_items,
            include_time=time_requested,
            include_overview_category=operational_overview,
        )
        if relation in {
            TurnKind.FILTER_CHANGE,
            TurnKind.TIME_CHANGE,
            *reuse_relations,
        } and isinstance(active_context, dict):
            active_dimensions = active_context.get("dimension_ids", ())
            if isinstance(active_dimensions, list):
                selected_dimensions = tuple(
                    dict.fromkeys(
                        [
                            *selected_dimensions,
                            *(str(item) for item in active_dimensions if str(item) in fields),
                        ]
                    )
                )
        selected_time_field = next(
            (
                str(item["item_id"])
                for item in field_items
                if self._is_time_field(item) and str(item["item_id"]) in selected_dimensions
            ),
            None,
        )
        filters = (
            ()
            if relation in reuse_relations
            else self._explicit_filters(message, selected_dimensions, field_items, payload)
        )
        if (
            not filters
            and relation
            in {
                TurnKind.TIME_CHANGE,
                TurnKind.DIMENSION_CHANGE,
                *reuse_relations,
            }
            and (isinstance(active_context, dict))
        ):
            summaries = active_context.get("filter_summary", ())
            if isinstance(summaries, list):
                inherited: list[FilterIntent] = []
                for summary in summaries:
                    parts = str(summary).split(":", 2)
                    if len(parts) == 3 and parts[0] in fields:
                        inherited.append(
                            FilterIntent.model_validate(
                                {
                                    "field_id": parts[0],
                                    "operator": parts[1],
                                    "values": tuple(item for item in parts[2].split(",") if item),
                                },
                                strict=False,
                            )
                        )
                filters = tuple(inherited)
        if "失败原因" in message:
            failure_filter = self._failure_filter(field_items, payload)
            if failure_filter is not None:
                filters = (*filters, failure_filter)

        clarification: Clarification | None = None
        tasks: tuple[AnalyticalTask, ...] = ()
        decisions: tuple[MetricDecision, ...] = ()
        if not datasets:
            clarification = Clarification(
                question="当前语义包中没有可用数据集, 无法规划分析。",
                reason_code="NO_DATASET_CANDIDATE",
            )
        elif selected_metric is None:
            reason_code = (
                "MISSING_MEMBER_REGISTRY"
                if "没有数据的Channel" in message
                else "UNKNOWN_FIELD"
                if "不存在字段" in message
                else "UNGOVERNED_PERCENTILE"
                if "P95" in message.upper() or "延迟" in message
                else "UNSUPPORTED_METRIC"
            )
            clarification = Clarification(
                question="当前语义口径不支持所询问的指标, 请选择已有指标。",
                reason_code=reason_code,
                allowed_answers=metrics,
            )
        else:
            selected_metrics = list(explicitly_selected_metrics or (selected_metric,))
            if relation in reuse_relations and isinstance(active_context, dict):
                active_metrics = active_context.get("metric_ids", ())
                if isinstance(active_metrics, list):
                    selected_metrics = [
                        str(item) for item in active_metrics if str(item) in metrics
                    ]
                    if not selected_metrics:
                        selected_metrics = [selected_metric]
            if operational_overview:
                overview_metrics = self._overview_metrics(metric_items)
                selected_metrics = list(dict.fromkeys([selected_metric, *overview_metrics]))
            volume_metric = self._metric_by_role(metric_items, "volume")
            decisions = tuple(
                MetricDecision(
                    metric_id=metric_id,
                    decision=(
                        "required"
                        if metric_id in (selected_metric, volume_metric)
                        else "recommended"
                    ),
                    role=(
                        "quality"
                        if self._metric_role(metric_id, metric_items) == "quality"
                        else "scale"
                    ),
                    reason=(
                        "发送运行概览同时需要规模与受治理质量视角"
                        if operational_overview
                        else "直接回答用户明确提出的分析目标"
                    ),
                    required_capabilities=selected_dimensions,
                    confidence=1.0,
                )
                for metric_id in selected_metrics
            )
            requested_methods: list[str] = []
            if operational_overview or selected_dimensions:
                requested_methods.extend(
                    item for item in ("rank", "contribution") if item in methods
                )
            if "失败原因" in message and "pareto" in methods:
                requested_methods.append("pareto")
            if "异常" in message and "mad_robust_zscore" in methods:
                requested_methods.append("mad_robust_zscore")
            if selected_time_field is not None:
                requested_methods.extend(
                    item
                    for item in ("period_change", "trend_slope", "moving_average")
                    if item in methods
                )
            inherited_grain: tuple[str, ...] = ()
            if relation in reuse_relations and isinstance(active_context, dict):
                raw_grain = active_context.get("grain", ())
                if isinstance(raw_grain, list):
                    inherited_grain = tuple(str(item) for item in raw_grain)
            field_by_id = {str(item["item_id"]): item for item in field_items}
            status_dimensions = tuple(
                item
                for item in selected_dimensions
                if self._is_status_field(field_by_id.get(item, {}))
            )
            category_dimensions = tuple(
                item
                for item in selected_dimensions
                if item != selected_time_field and item not in status_dimensions
            )
            if operational_overview and not status_dimensions:
                governed_status = next(
                    (str(item["item_id"]) for item in field_items if self._is_status_field(item)),
                    None,
                )
                if governed_status is not None:
                    status_dimensions = (governed_status,)

            requested_intents: list[str] = []
            if "异常" in message:
                requested_intents.append("anomaly")
            elif time_requested:
                requested_intents.append("time_trend")
            if "失败原因" in message:
                requested_intents.append("pareto")
            elif any(token in message.casefold() for token in ("排名", "排行", "top", "最高")):
                requested_intents.append("ranked_comparison")
            if any(token in message for token in ("构成", "组成", "结构", "占比")):
                requested_intents.append("composition")
            if operational_overview:
                requested_intents.extend(("time_trend", "ranked_comparison", "composition"))
            if not requested_intents:
                if selected_time_field is not None:
                    requested_intents.append("time_trend")
                elif selected_dimensions:
                    requested_intents.append("ranked_comparison")

            default_time_grain = (
                inherited_grain
                if inherited_grain
                else ("month",)
                if any(
                    word in message
                    for word in (
                        "5、6、7月",
                        "最近三个月",
                        "近三个月",
                        "过去三个月",
                        "月至",
                    )
                )
                else ("day",)
            )
            task_items: list[AnalyticalTask] = []
            for intent in dict.fromkeys(requested_intents):
                if intent in {"time_trend", "anomaly"}:
                    task_dimensions = tuple(
                        item
                        for item in (selected_time_field, *category_dimensions[:1])
                        if item is not None
                    )
                    task_methods = tuple(
                        item
                        for item in requested_methods
                        if item
                        in {
                            "period_change",
                            "trend_slope",
                            "moving_average",
                            "mad_robust_zscore",
                        }
                    )
                    analysis_type = "anomaly" if intent == "anomaly" else "trend"
                    task_grain = default_time_grain
                elif intent in {"ranked_comparison", "pareto"}:
                    task_dimensions = category_dimensions[:1] or status_dimensions[:1]
                    task_methods = tuple(
                        item
                        for item in requested_methods
                        if item in {"rank", "contribution", "pareto"}
                    )
                    analysis_type = "pareto" if intent == "pareto" else "comparison"
                    task_grain = ()
                else:
                    task_dimensions = tuple(
                        dict.fromkeys([*category_dimensions[:1], *status_dimensions[:1]])
                    )
                    task_methods = tuple(
                        item for item in requested_methods if item in {"rank", "contribution"}
                    )
                    analysis_type = "composition"
                    task_grain = ()
                if not task_dimensions:
                    continue
                task_items.append(
                    AnalyticalTask(
                        task_id=f"task_{intent}",
                        analytical_question=message,
                        analysis_type=analysis_type,
                        priority="required",
                        metric_ids=tuple(selected_metrics),
                        dimension_ids=task_dimensions,
                        grain=task_grain,
                        statistical_method_ids=task_methods,
                        visualization_intents=(intent,),
                        business_value="提供可核查的直接回答",
                    )
                )
            if not task_items:
                task_items.append(
                    AnalyticalTask(
                        task_id="task_summary",
                        analytical_question=message,
                        analysis_type="summary",
                        priority="required",
                        metric_ids=tuple(selected_metrics),
                        dimension_ids=selected_dimensions,
                        statistical_method_ids=tuple(dict.fromkeys(requested_methods)),
                        business_value="提供可核查的直接回答",
                    )
                )
            tasks = tuple(task_items)
            if relation in reuse_relations:
                raw_active_tasks = (
                    active_context.get("tasks", ()) if isinstance(active_context, dict) else ()
                )
                inherited_tasks = (
                    tuple(
                        AnalyticalTask.model_validate(item, strict=False)
                        for item in raw_active_tasks
                        if isinstance(item, dict)
                    )
                    if isinstance(raw_active_tasks, list)
                    else ()
                )
                if inherited_tasks:
                    tasks = inherited_tasks
                else:
                    # Compatibility for legacy persisted sessions. The formal reuse guard
                    # will requery if this union-shaped fallback cannot prove equivalence.
                    tasks = (
                        AnalyticalTask(
                            task_id="task_reuse_context",
                            analytical_question=message,
                            analysis_type=(
                                "presentation_change"
                                if relation == TurnKind.PRESENTATION_CHANGE
                                else "explanation"
                            ),
                            priority="required",
                            metric_ids=tuple(selected_metrics),
                            dimension_ids=selected_dimensions,
                            grain=inherited_grain,
                            business_value="复用既有验证数据回答连续追问",
                        ),
                    )

        raw_budget = payload.get("budgets")
        budget = (
            AnalysisBudget.model_validate(raw_budget, strict=False)
            if isinstance(raw_budget, dict)
            else AnalysisBudget()
        )
        return AnalysisPlanDraft(
            analysis_goal=message,
            question_archetype=(
                "operational_overview"
                if operational_overview
                else "trend"
                if time_requested
                else "breakdown"
                if selected_dimensions
                else "summary"
            ),
            turn_relation=relation,
            scope=AnalysisScope(
                dataset_ids=datasets[:1],
                time_range=time_range,
                filters=filters,
            ),
            metric_decisions=decisions,
            tasks=tasks,
            presentation_preference=PresentationPreference(
                requested_chart_type=cast(GovernedChartType | None, chart_preference.chart_type),
                user_specified=(
                    chart_preference.chart_type is not None or chart_preference.unsupported
                ),
                unsupported_chart_label=(
                    chart_preference.user_label if chart_preference.unsupported else None
                ),
            ),
            clarification=clarification,
            limitations=() if clarification is None else ("仅可使用当前语义候选",),
            budget=budget,
        )

    @staticmethod
    def _candidate_items(payload: dict[str, object], key: str) -> tuple[dict[str, object], ...]:
        raw = payload.get(key, ())
        if not isinstance(raw, list | tuple):
            return ()
        return tuple(
            item for item in raw if isinstance(item, dict) and isinstance(item.get("item_id"), str)
        )

    @classmethod
    def _candidate_ids(cls, payload: dict[str, object], key: str) -> tuple[str, ...]:
        return tuple(str(item["item_id"]) for item in cls._candidate_items(payload, key))

    @staticmethod
    def _metadata(item: dict[str, object]) -> dict[str, object]:
        raw = item.get("metadata")
        return raw if isinstance(raw, dict) else {}

    @classmethod
    def _is_time_field(cls, item: dict[str, object]) -> bool:
        metadata = cls._metadata(item)
        capabilities = item.get("capabilities", ())
        return metadata.get("semantic_type") == "time_dimension" or (
            isinstance(capabilities, list) and "date_histogram" in capabilities
        )

    @classmethod
    def _is_category_field(cls, item: dict[str, object]) -> bool:
        if cls._is_time_field(item):
            return False
        metadata = cls._metadata(item)
        semantic_type = metadata.get("semantic_type")
        capabilities = item.get("capabilities", ())
        return semantic_type == "categorical_dimension" or (
            semantic_type is None and isinstance(capabilities, list) and "group_by" in capabilities
        )

    @classmethod
    def _is_status_field(cls, item: dict[str, object]) -> bool:
        item_id = str(item.get("item_id", "")).rsplit(".", 1)[-1].casefold()
        display_name = str(item.get("display_name", "")).casefold()
        metadata = cls._metadata(item)
        aliases = metadata.get("aliases", ())
        alias_values = (
            {str(value).casefold() for value in aliases} if isinstance(aliases, list) else set()
        )
        return item_id == "status" or display_name == "status" or "状态" in alias_values

    @classmethod
    def _field_matches(cls, message: str, item: dict[str, object]) -> bool:
        metadata = cls._metadata(item)
        aliases = metadata.get("aliases", ())
        alias_values = aliases if isinstance(aliases, list) else []
        candidates = [
            str(item.get("display_name", "")),
            str(item.get("item_id", "")).rsplit(".", 1)[-1],
            *(str(value) for value in alias_values),
        ]
        lowered = message.casefold()
        return any(
            value and len(value) >= 2 and value.casefold() in lowered for value in candidates
        )

    @classmethod
    def _select_dimensions(
        cls,
        message: str,
        field_items: tuple[dict[str, object], ...],
        *,
        include_time: bool,
        include_overview_category: bool,
    ) -> tuple[str, ...]:
        selected: list[str] = []
        time_item = next((item for item in field_items if cls._is_time_field(item)), None)
        if include_time and time_item is not None:
            selected.append(str(time_item["item_id"]))
        for item in field_items:
            capabilities = item.get("capabilities", ())
            if (
                isinstance(capabilities, list)
                and "group_by" in capabilities
                and cls._field_matches(message, item)
            ):
                selected.append(str(item["item_id"]))
        if any(token in message for token in ("原因", "根因")):
            causal_dimension = next(
                (
                    item
                    for item in field_items
                    if cls._is_category_field(item)
                    and any(
                        token
                        in (f"{item.get('display_name', '')} {item.get('summary', '')}").casefold()
                        for token in ("原因", "错误", "error", "failure")
                    )
                ),
                None,
            )
            if causal_dimension is not None:
                selected.append(str(causal_dimension["item_id"]))
        if include_overview_category and not any(
            cls._is_category_field(item)
            and not cls._is_status_field(item)
            and str(item["item_id"]) in selected
            for item in field_items
        ):
            category = next(
                iter(
                    sorted(
                        (
                            item
                            for item in field_items
                            if cls._is_category_field(item) and not cls._is_status_field(item)
                        ),
                        key=lambda item: (
                            cls._metadata(item).get("maturity") != "BUSINESS_CONFIRMED",
                            -(
                                float(score)
                                if isinstance((score := item.get("score")), int | float)
                                else 0.0
                            ),
                            str(item["item_id"]),
                        ),
                    )
                ),
                None,
            )
            if category is not None:
                selected.append(str(category["item_id"]))
        return tuple(dict.fromkeys(selected))

    @classmethod
    def _explicit_filters(
        cls,
        message: str,
        selected_dimensions: tuple[str, ...],
        field_items: tuple[dict[str, object], ...],
        payload: dict[str, object],
    ) -> tuple[FilterIntent, ...]:
        del payload
        member_tokens = tuple(
            token
            for token in re.findall(r"(?<![A-Za-z0-9])[A-Z][A-Z0-9_-]{1,20}", message)
            if token not in {"TOP", "P95", "BI"}
        )
        if not member_tokens:
            return ()
        target = next(
            (
                str(item["item_id"])
                for item in field_items
                if str(item["item_id"]) in selected_dimensions
                and cls._is_category_field(item)
                and not cls._is_status_field(item)
            ),
            None,
        )
        if target is None:
            return ()
        return (FilterIntent(field_id=target, operator="in", values=member_tokens),)

    @classmethod
    def _failure_filter(
        cls,
        field_items: tuple[dict[str, object], ...],
        payload: dict[str, object],
    ) -> FilterIntent | None:
        values = cls._candidate_items(payload, "candidate_values")
        failures = tuple(
            item for item in values if "failure" in str(item.get("summary", "")).casefold()
        )
        source_ids = {str(cls._metadata(item).get("source_field_id", "")) for item in failures}
        source_field = next(
            (str(item["item_id"]) for item in field_items if str(item["item_id"]) in source_ids),
            None,
        )
        members = tuple(str(item.get("display_name", "")) for item in failures)
        members = tuple(item for item in members if item)
        if source_field is None or not members:
            return None
        return FilterIntent(field_id=source_field, operator="in", values=members)

    @staticmethod
    def _metric_role(metric_id: str, metric_items: tuple[dict[str, object], ...]) -> str:
        item = next(
            (candidate for candidate in metric_items if candidate.get("item_id") == metric_id),
            {},
        )
        text = " ".join(
            (str(item.get("display_name", "")), str(item.get("summary", "")))
        ).casefold()
        if any(token in text for token in ("率", "比例", "rate", "quality", "失败")):
            return "quality"
        return "volume"

    @classmethod
    def _metric_by_role(cls, metric_items: tuple[dict[str, object], ...], role: str) -> str | None:
        return next(
            (
                str(item["item_id"])
                for item in metric_items
                if cls._metric_role(str(item["item_id"]), metric_items) == role
            ),
            None,
        )

    @classmethod
    def _overview_metrics(cls, metric_items: tuple[dict[str, object], ...]) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                item
                for role in ("volume", "quality")
                if (item := cls._metric_by_role(metric_items, role)) is not None
            )
        )

    @classmethod
    def _select_metric(
        cls, message: str, metric_items: tuple[dict[str, object], ...]
    ) -> str | None:
        if any(
            token in message
            for token in ("点击率", "成功率", "没有数据的Channel", "不存在字段", "延迟P95")
        ):
            return None
        explicit = next(
            (str(item["item_id"]) for item in metric_items if cls._field_matches(message, item)),
            None,
        )
        return (
            explicit
            or cls._metric_by_role(metric_items, "volume")
            or (str(metric_items[0]["item_id"]) if metric_items else None)
        )

    @classmethod
    def _mock_turn_kind(cls, message: str, payload: dict[str, object]) -> TurnKind:
        """Deterministically simulate Agent A only inside the Mock LLM adapter."""

        classification = payload.get("turn_classification")
        details = classification if isinstance(classification, dict) else {}
        provisional = str(details.get("provisional_hint", TurnKind.NEW_ANALYSIS.value))
        if provisional == TurnKind.CLARIFICATION.value:
            return TurnKind.CLARIFICATION
        has_previous = details.get("has_previous_answer") is True
        if not has_previous:
            return TurnKind.NEW_ANALYSIS
        normalized = message.strip()
        if normalized.startswith(("新问题", "另外", "重新分析")):
            return TurnKind.NEW_TOPIC
        chart_preference = parse_chart_preference(normalized)
        if chart_preference.chart_type is not None or chart_preference.unsupported:
            semantic_items = (
                *cls._candidate_items(payload, "candidate_metrics"),
                *cls._candidate_items(payload, "candidate_fields"),
            )
            changes_data_request = any(
                cls._field_matches(normalized, item) for item in semantic_items
            ) or re.search(r"(?:20\d{2}年)?(?:1[0-2]|[1-9])月|最近|过去|近\s*\d+", normalized)
            if not changes_data_request:
                return TurnKind.PRESENTATION_CHANGE
            return TurnKind.NEW_ANALYSIS
        if normalized.startswith(("为什么", "解释", "依据")):
            return TurnKind.EXPLANATION
        if any(token in normalized for token in ("换成", "改成")) and "月" in normalized:
            return TurnKind.TIME_CHANGE
        if any(token in normalized for token in ("只看", "过滤", "排除")):
            return TurnKind.FILTER_CHANGE
        if any(token in normalized for token in ("改按", "换个维度", "按维度")):
            return TurnKind.DIMENSION_CHANGE
        return TurnKind.NEW_ANALYSIS

    @staticmethod
    def _time_range(message: str, payload: dict[str, object]) -> TimeRange:
        timezone = ZoneInfo("Asia/Hong_Kong")
        current_time = datetime.fromisoformat(str(payload["current_time"]).replace("Z", "+00:00"))
        range_match = re.search(
            r"(?:(20\d{2})年)?(1[0-2]|[1-9])月\s*(?:至|到|[-~—])\s*"
            r"(?:(20\d{2})年)?(1[0-2]|[1-9])月",
            message,
        )
        if range_match:
            local_year = current_time.astimezone(timezone).year
            start_year = int(range_match.group(1) or local_year)
            start_month = int(range_match.group(2))
            end_month = int(range_match.group(4))
            end_year = int(
                range_match.group(3) or (start_year + 1 if end_month < start_month else start_year)
            )
            end_exclusive = (
                datetime(end_year + 1, 1, 1, tzinfo=timezone)
                if end_month == 12
                else datetime(end_year, end_month + 1, 1, tzinfo=timezone)
            )
            return TimeRange(
                from_inclusive=datetime(start_year, start_month, 1, tzinfo=timezone),
                to_exclusive=end_exclusive,
                timezone="Asia/Hong_Kong",
            )
        if "5、6、7月" in message:
            return TimeRange(
                from_inclusive=datetime(2026, 5, 1, tzinfo=timezone),
                to_exclusive=datetime(2026, 8, 1, tzinfo=timezone),
                timezone="Asia/Hong_Kong",
            )
        if any(word in message for word in ("最近三个月", "近三个月", "过去三个月")):
            local_now = current_time.astimezone(timezone)
            end = datetime(local_now.year, local_now.month, 1, tzinfo=timezone)
            start_month_index = end.year * 12 + end.month - 1 - 3
            start = datetime(
                start_month_index // 12,
                start_month_index % 12 + 1,
                1,
                tzinfo=timezone,
            )
            return TimeRange(
                from_inclusive=start,
                to_exclusive=end,
                timezone="Asia/Hong_Kong",
            )
        month_match = re.search(r"(?:(20\d{2})年)?(1[0-2]|[1-9])月", message)
        if month_match:
            year = int(month_match.group(1) or current_time.astimezone(timezone).year)
            month = int(month_match.group(2))
        else:
            active = payload.get("session_active_context")
            if isinstance(active, dict) and isinstance(active.get("time_range"), dict):
                return TimeRange.model_validate(active["time_range"], strict=False)
            if isinstance(active, dict) and isinstance(active.get("time_summary"), str):
                summary = active["time_summary"]
                if summary.startswith("[") and summary.endswith(")") and "," in summary:
                    start_text, end_text = summary[1:-1].split(",", 1)
                    return TimeRange(
                        from_inclusive=datetime.fromisoformat(start_text),
                        to_exclusive=datetime.fromisoformat(end_text),
                        timezone="Asia/Hong_Kong",
                    )
            local_now = current_time.astimezone(timezone)
            year = local_now.year if local_now.month > 1 else local_now.year - 1
            month = local_now.month - 1 if local_now.month > 1 else 12
        start = datetime(year, month, 1, tzinfo=timezone)
        end = (
            datetime(year + 1, 1, 1, tzinfo=timezone)
            if month == 12
            else datetime(year, month + 1, 1, tzinfo=timezone)
        )
        return TimeRange(from_inclusive=start, to_exclusive=end, timezone="Asia/Hong_Kong")
