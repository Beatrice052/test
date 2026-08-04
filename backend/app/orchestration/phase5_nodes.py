"""Agent C proposal, deterministic grounding/dashboard/evidence, and atomic answer persistence."""

from __future__ import annotations

from datetime import UTC, datetime

from app.agents.insight_dashboard import InsightDashboardAgent
from app.contracts.analysis import AnswerStatus, TurnKind
from app.contracts.common import Provenance, semantic_hash
from app.contracts.dashboard import (
    DashboardBlock,
    DashboardSpec,
    VisualizationDefinition,
    VisualizationPreview,
)
from app.contracts.dataset import DatasetBundle, TabularDataset
from app.contracts.insight import ClaimBinding, ClaimDraft, ClaimSpec, InsightDashboardDraft
from app.contracts.metric import MetricDefinition
from app.contracts.session import ActiveAnalyticalContext, AnswerSnapshot
from app.orchestration.state import ChatBIState
from app.persistence.answer_repository import AnswerRepository
from app.persistence.ids import new_id
from app.persistence.session_repository import SessionRepository
from app.presentation.chart_preferences import (
    ChartPreference,
    apply_candidate_preference,
    block_supports_chart_type,
)
from app.presentation.dashboard import DashboardBuilder, chart_reading_guide
from app.presentation.evidence import EvidenceBuilder
from app.presentation.exploration import GovernedVisualizationExplorer
from app.presentation.grounding import ClaimGrounder, GroundingResult


class Phase5Nodes:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        answers: AnswerRepository,
        agent: InsightDashboardAgent,
        grounder: ClaimGrounder,
        dashboard_builder: DashboardBuilder,
        visualization_explorer: GovernedVisualizationExplorer,
        evidence_builder: EvidenceBuilder,
        metric_definitions: tuple[MetricDefinition, ...],
        visualization_definitions: tuple[VisualizationDefinition, ...],
        semantic_package_version: str,
    ) -> None:
        self.sessions = sessions
        self.answers = answers
        self.agent = agent
        self.grounder = grounder
        self.dashboard_builder = dashboard_builder
        self.visualization_explorer = visualization_explorer
        self.evidence_builder = evidence_builder
        self.metric_definitions = metric_definitions
        self.visualization_definitions = visualization_definitions
        self.semantic_package_version = semantic_package_version

    def reuse_answer(self, state: ChatBIState) -> dict[str, object]:
        """Create a new immutable answer from owned artifacts without executing a query."""

        session = state["session_context"]
        decision = state["turn_decision"]
        base_id = decision.analytical_base_answer_id or session.latest_answer_id
        if base_id is None:
            raise ValueError("reuse requires an analytical base answer")
        base = self.answers.get_answer(state["identity"].subject_id, base_id)
        dashboard = base.dashboard_spec
        reuse_warnings: tuple[str, ...] = ()
        if decision.turn_kind == TurnKind.PRESENTATION_CHANGE and dashboard is not None:
            dashboard, reuse_warnings = self._presentation_dashboard(
                dashboard, self._chart_preference(state), base.dataset_bundle
            )
        answer_id = new_id("ans")
        warnings = tuple(dict.fromkeys([*base.warnings, *reuse_warnings]))
        payload = {
            "session_id": session.object_id,
            "turn_kind": decision.turn_kind,
            "base_answer_id": base.object_id,
            "dashboard_hash": None if dashboard is None else dashboard.content_hash,
            "warnings": warnings,
        }
        snapshot = AnswerSnapshot(
            object_id=answer_id,
            created_at=datetime.now(UTC),
            content_hash=semantic_hash(payload),
            provenance=Provenance(
                producer="orchestration.phase5_reuse",
                source_ids=(base.object_id,),
            ),
            session_id=session.object_id,
            chronological_parent_answer_id=session.latest_answer_id,
            analytical_base_answer_id=base.object_id,
            turn_kind=decision.turn_kind,
            status=base.status,
            semantic_package_version=base.semantic_package_version,
            metric_versions=base.metric_versions,
            analysis_plan=base.analysis_plan,
            query_plan=base.query_plan,
            dataset_bundle=base.dataset_bundle,
            dashboard_spec=dashboard,
            visualization_previews=base.visualization_previews,
            claims=base.claims,
            evidence_package=base.evidence_package,
            limitations=base.limitations,
            warnings=warnings,
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
                "node": "reuse_answer",
                "terminal_status": "COMPLETED",
                "semantic_package_version": self.semantic_package_version,
                "answer_id": answer_id,
            },
        )
        return {"answer_snapshot": snapshot, "terminal_status": "COMPLETED"}

    @staticmethod
    def _presentation_dashboard(
        dashboard: DashboardSpec,
        preference: ChartPreference,
        bundle: DatasetBundle | None = None,
    ) -> tuple[DashboardSpec, tuple[str, ...]]:
        requested = preference.chart_type
        warnings: list[str] = []
        if preference.unsupported:
            warnings.append(
                f"requested chart type {preference.user_label} is outside the safe chart catalog"
            )
        blocks: list[DashboardBlock] = []
        for block in dashboard.blocks:
            if block.type != "chart" or requested is None:
                blocks.append(block)
                continue
            if requested in {"table", "pivot"}:
                blocks.append(
                    block.model_copy(
                        update={
                            "type": "pivot_table" if requested == "pivot" else "data_table",
                            "chart_type": requested,
                            "chart_analysis": None,
                        }
                    )
                )
                continue
            if not block_supports_chart_type(block, requested):
                blocks.append(
                    block.model_copy(
                        update={
                            "type": "data_table",
                            "chart_type": "table",
                            "chart_analysis": None,
                        }
                    )
                )
                warnings.append(
                    f"{requested} is incompatible with block {block.block_id}; "
                    "downgraded to data table"
                )
                continue
            chart_analysis = block.chart_analysis
            if chart_analysis is not None and block.encoding is not None:
                dataset = next(
                    (
                        item
                        for item in (() if bundle is None else bundle.datasets)
                        if item.object_id == block.dataset_id
                    ),
                    None,
                )
                chart_analysis = chart_analysis.model_copy(
                    update={
                        "reading_guide": chart_reading_guide(
                            requested,
                            block.encoding,
                            dimension_label=Phase5Nodes._display_label(
                                dataset, block.encoding.category or block.encoding.x
                            ),
                            measure_label=Phase5Nodes._display_label(
                                dataset, block.encoding.value or block.encoding.y
                            ),
                            series_label=Phase5Nodes._display_label(
                                dataset, block.encoding.series or block.encoding.color
                            ),
                        ),
                    }
                )
            blocks.append(
                block.model_copy(update={"chart_type": requested, "chart_analysis": chart_analysis})
            )
        payload = {
            "base_dashboard_id": dashboard.object_id,
            "requested": requested,
            "blocks": [item.model_dump(mode="json") for item in blocks],
            "warnings": [*dashboard.warnings, *warnings],
        }
        updated = DashboardSpec(
            object_id=new_id("dsh"),
            created_at=datetime.now(UTC),
            content_hash=semantic_hash(payload),
            provenance=Provenance(
                producer="presentation.reuse",
                source_ids=(dashboard.object_id,),
            ),
            title=dashboard.title,
            blocks=tuple(blocks),
            warnings=tuple(dict.fromkeys([*dashboard.warnings, *warnings])),
        )
        return updated, tuple(warnings)

    @staticmethod
    def _display_label(dataset: TabularDataset | None, column_name: str | None) -> str | None:
        if column_name is None:
            return None
        if dataset is None:
            return column_name.rsplit(".", 1)[-1]
        column = next((item for item in dataset.columns if item.name == column_name), None)
        if column is None:
            return column_name.rsplit(".", 1)[-1]
        return column.display_name or column.name.rsplit(".", 1)[-1]

    async def produce_answer(self, state: ChatBIState) -> dict[str, object]:
        exploration_failed = False
        preference_notes: tuple[str, ...] = ()
        try:
            exploration = await self.agent.explore(
                analysis_plan=state["analysis_plan"],
                bundle=state["dataset_bundle"],
                feature_summaries=state["feature_summaries"],
                metric_definitions=self.metric_definitions,
                visualization_definitions=self.visualization_definitions,
                correlation_id=state["correlation_id"],
                fixture_id=state.get("fixture_id"),
            )
            preferred_candidates, preference_notes = apply_candidate_preference(
                exploration.candidates,
                self.visualization_definitions,
                self._chart_preference(state),
            )
            previews = self.visualization_explorer.explore(
                preferred_candidates, state["dataset_bundle"]
            )
        except Exception:
            exploration_failed = True
            previews = ()
        agent_failed = False
        try:
            draft = await self.agent.plan(
                analysis_plan=state["analysis_plan"],
                bundle=state["dataset_bundle"],
                feature_summaries=state["feature_summaries"],
                metric_definitions=self.metric_definitions,
                visualization_definitions=self.visualization_definitions,
                visualization_previews=previews,
                correlation_id=state["correlation_id"],
                fixture_id=state.get("fixture_id"),
            )
        except Exception:
            agent_failed = True
            draft = InsightDashboardDraft(
                answer_summary="已取得验证数据, 洞察规划使用了确定性降级路径。",
                fallback_requested=True,
                limitations=("Insight planning adapter failed",),
            )
        grounding = self.grounder.ground(draft.claims, state["dataset_bundle"])
        completeness_errors = self._claim_completeness_errors(state, draft, grounding, previews)
        if (grounding.failures or completeness_errors) and not draft.fallback_requested:
            draft, grounding, completeness_errors = await self._repair_grounding(
                state, draft, grounding, completeness_errors, previews
            )
        if draft.fallback_requested or not grounding.claims:
            fallback_drafts = self._fallback_claims(state)
            fallback_grounding = self.grounder.ground(fallback_drafts, state["dataset_bundle"])
            claims = fallback_grounding.claims
            grounding_failures = (*grounding.failures, *fallback_grounding.failures)
            answer_summary = self._summary_from_claims(
                claims, fallback=self._fallback_summary(state)
            )
        else:
            claims = grounding.claims
            grounding_failures = grounding.failures
            answer_summary = self._summary_from_claims(claims, fallback=draft.answer_summary)
        limitations = tuple(
            dict.fromkeys(
                [
                    *state["analysis_plan"].limitations,
                    *draft.limitations,
                    *(("visualization exploration adapter failed",) if exploration_failed else ()),
                    *preference_notes,
                    *completeness_errors,
                ]
            )
        )
        dashboard = self.dashboard_builder.build(
            title=state["analysis_plan"].analysis_goal[:160],
            answer_summary=answer_summary,
            previews=previews if not agent_failed else (),
            visual_insights=draft.visual_insights if not agent_failed else (),
            claims=claims,
            bundle=state["dataset_bundle"],
            max_blocks=state["analysis_plan"].budget.max_blocks,
            kpi_metric_ids=tuple(
                item.metric_id
                for item in state["analysis_plan"].metric_decisions
                if item.decision in {"required", "recommended"}
            ),
            limitations=limitations,
            follow_up_suggestions=draft.follow_up_suggestions,
        )
        evidence = self.evidence_builder.build(
            analysis_plan=state["analysis_plan"],
            query_plan=state["query_plan"],
            compiled_queries=state["compiled_queries"],
            executions=state["execution_records"],
            bundle=state["dataset_bundle"],
            metric_definitions=self.metric_definitions,
            semantic_package_version=self.semantic_package_version,
        )
        partial = (
            agent_failed
            or exploration_failed
            or draft.fallback_requested
            or bool(grounding_failures)
            or bool(completeness_errors)
            or not state["dataset_bundle"].complete
        )
        status = AnswerStatus.PARTIAL if partial else AnswerStatus.ANSWERED
        warnings = tuple(
            dict.fromkeys(
                [*state["dataset_bundle"].warnings]
                + [item.message for item in grounding_failures]
                + list(completeness_errors)
                + (["deterministic insight fallback used"] if agent_failed else [])
                + (["visualization exploration unavailable"] if exploration_failed else [])
            )
        )
        answer_id = new_id("ans")
        payload = {
            "session_id": state["session_context"].object_id,
            "turn_kind": state["turn_decision"].turn_kind,
            "status": status,
            "semantic_package_version": self.semantic_package_version,
            "analysis_plan_hash": state["analysis_plan"].content_hash,
            "query_plan_hash": state["query_plan"].content_hash,
            "dataset_bundle_hash": state["dataset_bundle"].content_hash,
            "dashboard_hash": dashboard.content_hash,
            "evidence_hash": evidence.content_hash,
            "claim_hashes": [item.content_hash for item in claims],
            "warnings": warnings,
        }
        snapshot = AnswerSnapshot(
            object_id=answer_id,
            created_at=datetime.now(UTC),
            content_hash=semantic_hash(payload),
            provenance=Provenance(
                producer="orchestration.phase5_answer",
                source_ids=(
                    state["analysis_plan"].object_id,
                    state["query_plan"].object_id,
                    state["dataset_bundle"].object_id,
                    dashboard.object_id,
                    evidence.object_id,
                ),
            ),
            session_id=state["session_context"].object_id,
            chronological_parent_answer_id=state["session_context"].latest_answer_id,
            analytical_base_answer_id=state["turn_decision"].analytical_base_answer_id,
            turn_kind=state["turn_decision"].turn_kind,
            status=status,
            semantic_package_version=self.semantic_package_version,
            metric_versions=tuple(
                item for query in state["compiled_queries"] for item in query.semantics.metric_ids
            ),
            analysis_plan=state["analysis_plan"],
            query_plan=state["query_plan"],
            dataset_bundle=state["dataset_bundle"],
            dashboard_spec=dashboard,
            visualization_previews=previews,
            claims=claims,
            evidence_package=evidence,
            limitations=limitations,
            warnings=warnings,
        )
        active_context = self._active_context(state, answer_id)
        self.answers.persist_answer(
            state["identity"].subject_id,
            state["turn_id"],
            snapshot,
            active_context,
        )
        self.sessions.save_safe_state(
            state["identity"].subject_id,
            state["turn_id"],
            {
                "node": "produce_answer",
                "terminal_status": "COMPLETED",
                "semantic_package_version": self.semantic_package_version,
                "analysis_plan_id": state["analysis_plan"].object_id,
                "answer_id": answer_id,
            },
        )
        return {"answer_snapshot": snapshot, "terminal_status": "COMPLETED"}

    async def _repair_grounding(
        self,
        state: ChatBIState,
        draft: InsightDashboardDraft,
        grounding: GroundingResult,
        completeness_errors: tuple[str, ...],
        previews: tuple[VisualizationPreview, ...],
    ) -> tuple[InsightDashboardDraft, GroundingResult, tuple[str, ...]]:
        """Give Agent C at most two directed attempts to repair rejected claim bindings."""

        current_draft = draft
        current_grounding = grounding
        current_completeness = completeness_errors
        for attempt in range(1, 3):
            errors = (
                tuple(
                    f"{item.claim_index}:{item.code}:{item.message}"
                    for item in current_grounding.failures
                )
                + current_completeness
            )
            try:
                candidate = await self.agent.repair(
                    draft=current_draft,
                    errors=errors,
                    analysis_plan=state["analysis_plan"],
                    bundle=state["dataset_bundle"],
                    visualization_previews=previews,
                    attempt=attempt,
                    correlation_id=state["correlation_id"],
                    fixture_id=state.get("fixture_id"),
                )
            except Exception:
                break
            current_draft = candidate
            current_grounding = self.grounder.ground(current_draft.claims, state["dataset_bundle"])
            current_completeness = self._claim_completeness_errors(
                state, current_draft, current_grounding, previews
            )
            if not current_grounding.failures and not current_completeness:
                break
        return current_draft, current_grounding, current_completeness

    @staticmethod
    def _claim_completeness_errors(
        state: ChatBIState,
        draft: InsightDashboardDraft,
        grounding: GroundingResult,
        previews: tuple[VisualizationPreview, ...],
    ) -> tuple[str, ...]:
        task_ids = {item.task_id for item in state["analysis_plan"].tasks}
        required = {
            item.task_id for item in state["analysis_plan"].tasks if item.priority == "required"
        }
        errors: list[str] = []
        preview_by_id = {item.object_id: item for item in previews}
        draft_claim_ids = [item.claim_id for item in draft.claims]
        for claim_id in sorted(
            {item for item in draft_claim_ids if draft_claim_ids.count(item) > 1}
        ):
            errors.append(f"claim:DUPLICATE_CLAIM_ID:{claim_id}")
        declared_claim_ids = set(draft_claim_ids)
        insight_ids = [item.insight_id for item in draft.visual_insights]
        for insight_id in sorted({item for item in insight_ids if insight_ids.count(item) > 1}):
            errors.append(f"visual_insight:DUPLICATE_INSIGHT_ID:{insight_id}")
        selected_preview_ids = [item.preview_id for item in draft.visual_insights]
        for preview_id in sorted(
            {item for item in selected_preview_ids if selected_preview_ids.count(item) > 1}
        ):
            errors.append(f"visual_insight:DUPLICATE_PREVIEW:{preview_id}")
        grounded_by_id = {
            item.source_claim_id: item
            for item in grounding.claims
            if item.source_claim_id is not None
        }
        for insight in draft.visual_insights:
            preview = preview_by_id.get(insight.preview_id)
            if preview is None:
                errors.append(f"visual_insight:UNKNOWN_PREVIEW:{insight.insight_id}")
                continue
            if preview.decision == "REJECT":
                errors.append(f"visual_insight:REJECTED_PREVIEW:{insight.insight_id}")
            unknown_preview_tasks = set(preview.task_ids) - task_ids
            if unknown_preview_tasks:
                errors.append(
                    "visual_insight:UNKNOWN_TASK_ID:"
                    f"{insight.insight_id}:{','.join(sorted(unknown_preview_tasks))}"
                )
            unknown_claims = set(insight.claim_ids) - declared_claim_ids
            if unknown_claims:
                errors.append(
                    "visual_insight:UNKNOWN_CLAIM:"
                    f"{insight.insight_id}:{','.join(sorted(unknown_claims))}"
                )
            for claim_id in insight.claim_ids:
                claim = grounded_by_id.get(claim_id)
                if claim is None:
                    errors.append(
                        f"visual_insight:UNGROUNDED_CLAIM:{insight.insight_id}:{claim_id}"
                    )
                    continue
                if not set(preview.task_ids).intersection(claim.task_ids):
                    errors.append(f"visual_insight:TASK_MISMATCH:{insight.insight_id}:{claim_id}")
                if any(item.dataset_id != preview.dataset_id for item in claim.evidence_refs):
                    errors.append(
                        f"visual_insight:DATASET_MISMATCH:{insight.insight_id}:{claim_id}"
                    )
                if preview.encoding is not None:
                    measure_columns = {
                        item
                        for item in (preview.encoding.value, preview.encoding.y)
                        if item is not None
                    }
                    if measure_columns and not any(
                        item.column in measure_columns for item in claim.evidence_refs
                    ):
                        errors.append(
                            f"visual_insight:MEASURE_MISMATCH:{insight.insight_id}:{claim_id}"
                        )
        for index, claim in enumerate(grounding.claims):
            unknown = set(claim.task_ids) - task_ids
            if unknown:
                errors.append(f"{index}:UNKNOWN_TASK_ID:{','.join(sorted(unknown))}")
        covered = {
            task_id
            for claim in grounding.claims
            for task_id in claim.task_ids
            if task_id in task_ids
        }
        explicitly_limited = {
            task_id
            for task_id in required
            if any(task_id in limitation for limitation in draft.limitations)
        }
        for task_id in sorted(required - covered - explicitly_limited):
            errors.append(f"coverage:MISSING_REQUIRED_TASK:{task_id}")
        if (
            any(item.rows for item in state["dataset_bundle"].datasets)
            and grounding.claims
            and not any(item.importance == "primary" for item in grounding.claims)
        ):
            errors.append("coverage:MISSING_PRIMARY_CLAIM")
        return tuple(errors)

    @staticmethod
    def _chart_preference(state: ChatBIState) -> ChartPreference:
        preference = state["analysis_plan"].presentation_preference
        return ChartPreference(
            chart_type=preference.requested_chart_type,
            user_label=(preference.requested_chart_type or preference.unsupported_chart_label),
            unsupported=preference.unsupported_chart_label is not None,
        )

    @staticmethod
    def _fallback_claims(state: ChatBIState) -> tuple[ClaimDraft, ...]:
        dataset = Phase5Nodes._primary_dataset(state)
        if not dataset.rows:
            return ()
        measure = next(
            (
                item
                for item in dataset.columns
                if item.semantic_role in {"metric", "measure"} and item.semantic_role != "metadata"
            ),
            None,
        )
        if measure is None:
            return ()
        selector = "first" if len(dataset.rows) == 1 else f"argmax:{measure.name}"
        dimension = next(
            (item for item in dataset.columns if item.semantic_role == "dimension"), None
        )
        bindings = []
        template = "已验证值为 {value}。"
        if dimension is not None:
            bindings.append(
                ClaimBinding(
                    name="category",
                    dataset_id=dataset.dataset_id,
                    selector=selector,
                    column=dimension.name,
                )
            )
            template = "已验证结果中 {category} 的数值最高, 为 {value}。"
        bindings.append(
            ClaimBinding(
                name="value",
                dataset_id=dataset.dataset_id,
                selector=selector,
                column=measure.name,
            )
        )
        return (
            ClaimDraft(
                claim_id="claim_deterministic_fallback",
                claim_type="value" if len(dataset.rows) == 1 else "ranking",
                template=template,
                importance="primary",
                task_ids=tuple(
                    item.task_id
                    for item in state["analysis_plan"].tasks
                    if item.priority == "required"
                ),
                bindings=tuple(bindings),
            ),
        )

    @staticmethod
    def _fallback_summary(state: ChatBIState) -> str:
        dataset = Phase5Nodes._primary_dataset(state)
        if not dataset.rows:
            return "所选时间与过滤范围内没有匹配记录。"
        return "已展示通过确定性证据绑定的验证结果。"

    @staticmethod
    def _summary_from_claims(claims: tuple[ClaimSpec, ...], *, fallback: str) -> str:
        # Claim order is Agent C's answer narrative order. Every sentence is grounded
        # first, so the total analysis can be complete without trusting free-form
        # model prose or repeating the same findings in a second section.
        selected: list[str] = []
        seen: set[str] = set()
        for claim in claims:
            normalized = "".join(
                character.casefold() for character in claim.text if character.isalnum()
            )
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            selected.append(claim.text)
        return " ".join(selected) or fallback

    @staticmethod
    def _primary_dataset(state: ChatBIState) -> TabularDataset:
        datasets = state["dataset_bundle"].datasets
        return next(
            (item for item in reversed(datasets) if item.kind == "derived"),
            datasets[0],
        )

    @staticmethod
    def _active_context(state: ChatBIState, answer_id: str) -> ActiveAnalyticalContext:
        analysis = state["analysis_plan"]
        return ActiveAnalyticalContext(
            analytical_base_answer_id=answer_id,
            dataset_ids=analysis.scope.dataset_ids,
            metric_ids=tuple(
                item.metric_id for item in analysis.metric_decisions if item.decision != "rejected"
            ),
            dimension_ids=tuple(
                dict.fromkeys(
                    dimension for task in analysis.tasks for dimension in task.dimension_ids
                )
            ),
            grain=tuple(dict.fromkeys(item for task in analysis.tasks for item in task.grain)),
            filter_summary=tuple(
                f"{item.field_id}:{item.operator}:{','.join(map(str, item.values))}"
                for item in analysis.scope.filters
            ),
            time_summary=(
                f"[{analysis.scope.time_range.from_inclusive.isoformat()},"
                f"{analysis.scope.time_range.to_exclusive.isoformat()})"
            ),
        )
