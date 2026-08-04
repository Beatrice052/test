"""Agent C proposal, deterministic grounding/dashboard/evidence, and atomic answer persistence."""

from __future__ import annotations

from datetime import UTC, datetime

from app.agents.insight_dashboard import InsightDashboardAgent
from app.analytics.governed_tool import GovernedAnalyticsTool
from app.contracts.analysis import AnswerStatus, TurnKind
from app.contracts.common import Provenance, semantic_hash
from app.contracts.dashboard import (
    DashboardBlock,
    DashboardSpec,
    VisualizationCandidate,
    VisualizationDefinition,
    VisualizationPreview,
)
from app.contracts.dataset import DatasetBundle, TabularDataset
from app.contracts.insight import (
    AnalyticsToolResult,
    ClaimBinding,
    ClaimDraft,
    ClaimSpec,
    FeatureSummary,
    InsightDashboardDraft,
    KpiSelectionDraft,
    VisualInsightDraft,
)
from app.contracts.metric import MethodDefinition, MetricDefinition
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
        method_definitions: tuple[MethodDefinition, ...],
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
        self.method_definitions = method_definitions
        self.analytics_tool = GovernedAnalyticsTool(method_definitions)
        self.visualization_definitions = visualization_definitions
        self.semantic_package_version = semantic_package_version

    async def reuse_answer(self, state: ChatBIState) -> dict[str, object]:
        """Create a new immutable answer from owned artifacts without executing a query."""

        session = state["session_context"]
        decision = state["turn_decision"]
        base_id = decision.analytical_base_answer_id or session.latest_answer_id
        if base_id is None:
            raise ValueError("reuse requires an analytical base answer")
        base = self.answers.get_answer(state["identity"].subject_id, base_id)
        dashboard = base.dashboard_spec
        previews = base.visualization_previews
        claims = base.claims
        overall_claim_ids = base.overall_claim_ids
        kpi_selections = base.kpi_selections
        limitations = base.limitations
        reuse_warnings: tuple[str, ...] = ()
        if (
            decision.turn_kind == TurnKind.PRESENTATION_CHANGE
            and dashboard is not None
            and base.dataset_bundle is not None
        ):
            dashboard, previews, reuse_warnings = await self._replan_presentation(state, base)
        elif (
            decision.turn_kind == TurnKind.EXPLANATION
            and dashboard is not None
            and base.dataset_bundle is not None
        ):
            (
                dashboard,
                claims,
                overall_claim_ids,
                kpi_selections,
                limitations,
                reuse_warnings,
            ) = await self._explain_reused_data(state, base)
        answer_id = new_id("ans")
        warnings = tuple(dict.fromkeys([*base.warnings, *reuse_warnings]))
        status = (
            AnswerStatus.PARTIAL
            if any(
                marker in warning.casefold()
                for warning in reuse_warnings
                for marker in ("failed", "unavailable")
            )
            else base.status
        )
        payload = {
            "session_id": session.object_id,
            "turn_kind": decision.turn_kind,
            "base_answer_id": base.object_id,
            "analysis_plan_hash": state["analysis_plan"].content_hash,
            "dashboard_hash": None if dashboard is None else dashboard.content_hash,
            "visualization_preview_hashes": [item.content_hash for item in previews],
            "claim_hashes": [item.content_hash for item in claims],
            "overall_claim_ids": overall_claim_ids,
            "kpi_selection_ids": [item.selection_id for item in kpi_selections],
            "limitations": limitations,
            "status": status,
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
            status=status,
            semantic_package_version=base.semantic_package_version,
            metric_versions=base.metric_versions,
            analysis_plan=state["analysis_plan"],
            query_plan=base.query_plan,
            dataset_bundle=base.dataset_bundle,
            feature_summaries=base.feature_summaries,
            analytics_tool_results=base.analytics_tool_results,
            dashboard_spec=dashboard,
            visualization_previews=previews,
            claims=claims,
            overall_claim_ids=overall_claim_ids,
            kpi_selections=kpi_selections,
            evidence_package=base.evidence_package,
            limitations=limitations,
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

    async def _explain_reused_data(
        self,
        state: ChatBIState,
        base: AnswerSnapshot,
    ) -> tuple[
        DashboardSpec,
        tuple[ClaimSpec, ...],
        tuple[str, ...],
        tuple[KpiSelectionDraft, ...],
        tuple[str, ...],
        tuple[str, ...],
    ]:
        """Answer an explanation follow-up from immutable data without another query."""

        assert base.dashboard_spec is not None
        assert base.dataset_bundle is not None
        if not base.feature_summaries:
            return (
                base.dashboard_spec,
                base.claims,
                base.overall_claim_ids,
                base.kpi_selections,
                base.limitations,
                ("explanation synthesis unavailable for a legacy answer",),
            )
        try:
            draft = await self.agent.plan(
                analysis_plan=state["analysis_plan"],
                bundle=base.dataset_bundle,
                feature_summaries=base.feature_summaries,
                metric_definitions=self.metric_definitions,
                method_definitions=self.method_definitions,
                visualization_definitions=self.visualization_definitions,
                visualization_previews=base.visualization_previews,
                analytics_tool_results=base.analytics_tool_results,
                correlation_id=state["correlation_id"],
                fixture_id=state.get("fixture_id"),
            )
            grounding = self.grounder.ground(
                draft.claims,
                base.dataset_bundle,
                feature_summaries=base.feature_summaries,
            )
            validation_state = dict(state)
            validation_state["dataset_bundle"] = base.dataset_bundle
            completeness = self._claim_completeness_errors(
                validation_state,  # type: ignore[arg-type]
                draft,
                grounding,
                base.visualization_previews,
            )
            for attempt in range(1, 3):
                if not grounding.failures and not completeness:
                    break
                errors = tuple(
                    [
                        *(
                            f"{item.claim_index}:{item.code}:{item.message}"
                            for item in grounding.failures
                        ),
                        *completeness,
                    ]
                )
                draft = await self.agent.repair(
                    draft=draft,
                    errors=errors,
                    analysis_plan=state["analysis_plan"],
                    bundle=base.dataset_bundle,
                    feature_summaries=base.feature_summaries,
                    visualization_previews=base.visualization_previews,
                    attempt=attempt,
                    correlation_id=state["correlation_id"],
                    fixture_id=state.get("fixture_id"),
                )
                grounding = self.grounder.ground(
                    draft.claims,
                    base.dataset_bundle,
                    feature_summaries=base.feature_summaries,
                )
                completeness = self._claim_completeness_errors(
                    validation_state,  # type: ignore[arg-type]
                    draft,
                    grounding,
                    base.visualization_previews,
                )
            if not grounding.claims:
                raise ValueError("explanation produced no grounded claims")
            visual_insights = draft.visual_insights or self._reuse_visual_insights(
                base.visualization_previews,
                grounding.claims,
            )
            summary_claims = self._claims_for_ids(grounding.claims, draft.overall_claim_ids)
            limitations = tuple(dict.fromkeys([*base.limitations, *draft.limitations]))
            dashboard = self.dashboard_builder.build(
                title=state["analysis_plan"].analysis_goal[:160],
                answer_summary=self._summary_from_claims(
                    summary_claims,
                    fallback=draft.answer_summary,
                ),
                previews=base.visualization_previews,
                visual_insights=visual_insights,
                claims=grounding.claims,
                summary_claims=summary_claims,
                bundle=base.dataset_bundle,
                max_blocks=state["analysis_plan"].budget.max_blocks,
                kpi_selections=draft.kpi_selections,
                limitations=limitations,
                follow_up_suggestions=draft.follow_up_suggestions,
                ensure_result_table=bool(grounding.failures or completeness),
            )
            warnings = tuple(
                [
                    *(item.message for item in grounding.failures),
                    *completeness,
                ]
            )
            return (
                dashboard,
                grounding.claims,
                draft.overall_claim_ids,
                draft.kpi_selections,
                limitations,
                warnings,
            )
        except Exception:
            return (
                base.dashboard_spec,
                base.claims,
                base.overall_claim_ids,
                base.kpi_selections,
                base.limitations,
                ("explanation synthesis adapter failed; previous verified answer retained",),
            )

    async def _replan_presentation(
        self,
        state: ChatBIState,
        base: AnswerSnapshot,
    ) -> tuple[DashboardSpec, tuple[VisualizationPreview, ...], tuple[str, ...]]:
        """Re-run only Agent C visual exploration over immutable reused data."""

        assert base.dashboard_spec is not None
        assert base.dataset_bundle is not None
        preference = self._chart_preference(state)
        warnings: list[str] = []
        if preference.unsupported:
            warnings.append(
                f"requested chart type {preference.user_label} is outside the safe chart catalog"
            )
        if not base.feature_summaries:
            dashboard, fallback_warnings = self._presentation_dashboard(
                base.dashboard_spec,
                preference,
                base.dataset_bundle,
            )
            return (
                dashboard,
                base.visualization_previews,
                (
                    *warnings,
                    "presentation replanning unavailable for a legacy answer",
                    *fallback_warnings,
                ),
            )
        try:
            exploration = await self.agent.explore(
                analysis_plan=state["analysis_plan"],
                bundle=base.dataset_bundle,
                feature_summaries=base.feature_summaries,
                metric_definitions=self.metric_definitions,
                method_definitions=self.method_definitions,
                visualization_definitions=self.visualization_definitions,
                correlation_id=state["correlation_id"],
                fixture_id=state.get("fixture_id"),
            )
            preferred_candidates, preference_notes = apply_candidate_preference(
                exploration.candidates,
                self.visualization_definitions,
                preference,
            )
            previews = self.visualization_explorer.explore(
                preferred_candidates,
                base.dataset_bundle,
                analysis_plan=state["analysis_plan"],
            )
            previews, visual_warnings = self._ensure_required_visualization(
                state,
                previews,
                original_candidates=exploration.candidates,
                bundle=base.dataset_bundle,
            )
            visual_insights = self._reuse_visual_insights(previews, base.claims)
            follow_ups = tuple(
                suggestion
                for block in base.dashboard_spec.blocks
                if block.type == "follow_up_suggestions"
                for suggestion in block.suggestions
            )
            dashboard = self.dashboard_builder.build(
                title=state["analysis_plan"].analysis_goal[:160],
                answer_summary=self._dashboard_summary(base.dashboard_spec),
                previews=previews,
                visual_insights=visual_insights,
                claims=base.claims,
                summary_claims=self._claims_for_ids(base.claims, base.overall_claim_ids),
                bundle=base.dataset_bundle,
                max_blocks=state["analysis_plan"].budget.max_blocks,
                kpi_selections=base.kpi_selections,
                limitations=tuple(
                    dict.fromkeys(
                        [
                            *base.limitations,
                            *exploration.limitations,
                        ]
                    )
                ),
                follow_up_suggestions=follow_ups,
                ensure_result_table=True,
            )
            warnings.extend((*preference_notes, *visual_warnings))
            if not previews:
                warnings.append("presentation exploration returned no feasible preview")
            return dashboard, previews, tuple(warnings)
        except Exception:
            dashboard, fallback_warnings = self._presentation_dashboard(
                base.dashboard_spec,
                preference,
                base.dataset_bundle,
            )
            return (
                dashboard,
                base.visualization_previews,
                (*warnings, "presentation exploration adapter failed", *fallback_warnings),
            )

    def _ensure_required_visualization(
        self,
        state: ChatBIState,
        previews: tuple[VisualizationPreview, ...],
        *,
        original_candidates: tuple[VisualizationCandidate, ...],
        bundle: DatasetBundle,
    ) -> tuple[tuple[VisualizationPreview, ...], tuple[str, ...]]:
        """Keep ChatBI visual-first without making a business-specific chart rule.

        Agent C remains the decision maker.  This guard only retries Agent C's
        *unmodified* candidate when an explicit table/incompatible chart preference
        turned it into a table.  It never invents a candidate from a hard-coded
        data shape: if C supplied no feasible chart, the answer is transparently
        partial and the real-LLM quality gate must correct the agent behavior.
        """

        if not any(item.rows for item in bundle.datasets):
            return previews, ()
        if self._has_chart_preview(previews):
            return previews, ()
        fallback_previews = self.visualization_explorer.explore(
            original_candidates,
            bundle,
            analysis_plan=state["analysis_plan"],
        )
        charts = tuple(item for item in fallback_previews if self._is_chart_preview(item))
        if charts:
            return (*previews, *charts), (
                "a readable governed chart was retained alongside the requested tabular fallback",
            )
        return previews, (
            "Agent C did not produce a feasible governed chart for non-empty data; "
            "the answer is marked partial instead of a program-selected chart being invented",
        )

    @staticmethod
    def _is_chart_preview(preview: VisualizationPreview) -> bool:
        return (
            preview.decision in {"ACCEPT", "ACCEPT_WITH_TRANSFORM"}
            and preview.renderer == "echarts_contract"
            and preview.chart_type not in {None, "table", "pivot"}
            and preview.encoding is not None
        )

    @classmethod
    def _has_chart_preview(cls, previews: tuple[VisualizationPreview, ...]) -> bool:
        return any(cls._is_chart_preview(item) for item in previews)

    @staticmethod
    def _reuse_visual_insights(
        previews: tuple[VisualizationPreview, ...],
        claims: tuple[ClaimSpec, ...],
    ) -> tuple[VisualInsightDraft, ...]:
        """Bind reused claims only by exact task, Dataset, and measure identities."""

        insights: list[VisualInsightDraft] = []
        for index, preview in enumerate(previews, start=1):
            measure_columns = {
                item
                for item in (
                    None if preview.encoding is None else preview.encoding.value,
                    None if preview.encoding is None else preview.encoding.y,
                )
                if item is not None
            }
            claim_ids = tuple(
                claim.source_claim_id
                for claim in claims
                if claim.source_claim_id is not None
                and set(preview.task_ids).intersection(claim.task_ids)
                and claim.evidence_refs
                and all(
                    evidence.dataset_id == preview.dataset_id for evidence in claim.evidence_refs
                )
                and (
                    not measure_columns
                    or any(evidence.column in measure_columns for evidence in claim.evidence_refs)
                )
            )
            if not claim_ids:
                continue
            insights.append(
                VisualInsightDraft(
                    insight_id=f"reuse_insight_{index}",
                    preview_id=preview.object_id,
                    claim_ids=claim_ids,
                    purpose=preview.purpose,
                    caveats=(preview.reason,)
                    if preview.decision in {"DOWNGRADE_TO_TABLE", "REJECT"}
                    else (),
                )
            )
        return tuple(insights)

    @staticmethod
    def _dashboard_summary(dashboard: DashboardSpec) -> str:
        summary = next((item for item in dashboard.blocks if item.type == "answer_summary"), None)
        value = None if summary is None else summary.content.get("text")
        return str(value) if isinstance(value, str) else "已复用上轮验证结果。"

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
        analytics_tool_results: tuple[AnalyticsToolResult, ...] = ()
        analysis_feature_summaries = state["feature_summaries"]
        analytics_warnings: tuple[str, ...] = ()
        try:
            exploration = await self.agent.explore(
                analysis_plan=state["analysis_plan"],
                bundle=state["dataset_bundle"],
                feature_summaries=state["feature_summaries"],
                metric_definitions=self.metric_definitions,
                method_definitions=self.method_definitions,
                visualization_definitions=self.visualization_definitions,
                correlation_id=state["correlation_id"],
                fixture_id=state.get("fixture_id"),
            )
            analytics_execution = self.analytics_tool.execute(
                exploration.analytics_requests,
                analysis_plan=state["analysis_plan"],
                bundle=state["dataset_bundle"],
                feature_summaries=state["feature_summaries"],
            )
            analytics_tool_results = analytics_execution.results
            analysis_feature_summaries = analytics_execution.feature_summaries
            analytics_warnings = analytics_execution.warnings
            preferred_candidates, preference_notes = apply_candidate_preference(
                exploration.candidates,
                self.visualization_definitions,
                self._chart_preference(state),
            )
            previews = self.visualization_explorer.explore(
                preferred_candidates,
                state["dataset_bundle"],
                analysis_plan=state["analysis_plan"],
            )
            previews, visual_warnings = self._ensure_required_visualization(
                state,
                previews,
                original_candidates=exploration.candidates,
                bundle=state["dataset_bundle"],
            )
        except Exception:
            exploration_failed = True
            previews = ()
            visual_warnings = ("visualization exploration adapter failed",)
        agent_failed = False
        try:
            draft = await self.agent.plan(
                analysis_plan=state["analysis_plan"],
                bundle=state["dataset_bundle"],
                feature_summaries=analysis_feature_summaries,
                metric_definitions=self.metric_definitions,
                method_definitions=self.method_definitions,
                visualization_definitions=self.visualization_definitions,
                visualization_previews=previews,
                analytics_tool_results=analytics_tool_results,
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
        grounding = self.grounder.ground(
            draft.claims,
            state["dataset_bundle"],
            feature_summaries=analysis_feature_summaries,
        )
        completeness_errors = self._claim_completeness_errors(state, draft, grounding, previews)
        if (grounding.failures or completeness_errors) and not draft.fallback_requested:
            draft, grounding, completeness_errors = await self._repair_grounding(
                state,
                draft,
                grounding,
                completeness_errors,
                previews,
                feature_summaries=analysis_feature_summaries,
            )
        if draft.fallback_requested or not grounding.claims:
            fallback_drafts = self._fallback_claims(state)
            fallback_grounding = self.grounder.ground(
                fallback_drafts,
                state["dataset_bundle"],
                feature_summaries=state["feature_summaries"],
            )
            claims = fallback_grounding.claims
            grounding_failures = (*grounding.failures, *fallback_grounding.failures)
            overall_claim_ids = tuple(
                item.source_claim_id for item in claims if item.source_claim_id is not None
            )
            summary_claims = claims
            answer_summary = self._summary_from_claims(
                summary_claims, fallback=self._fallback_summary(state)
            )
        else:
            claims = grounding.claims
            grounding_failures = grounding.failures
            overall_claim_ids = draft.overall_claim_ids
            summary_claims = self._claims_for_ids(claims, overall_claim_ids)
            answer_summary = self._summary_from_claims(
                summary_claims, fallback=draft.answer_summary
            )
        analytical_limitations = tuple(
            dict.fromkeys(
                [
                    *state["analysis_plan"].limitations,
                    *((*draft.limitations,) if not agent_failed else ()),
                ]
            )
        )
        dashboard = self.dashboard_builder.build(
            title=state["analysis_plan"].analysis_goal[:160],
            answer_summary=answer_summary,
            previews=previews if not agent_failed else (),
            visual_insights=draft.visual_insights if not agent_failed else (),
            claims=claims,
            summary_claims=summary_claims,
            bundle=state["dataset_bundle"],
            max_blocks=state["analysis_plan"].budget.max_blocks,
            kpi_selections=() if agent_failed else draft.kpi_selections,
            limitations=analytical_limitations,
            follow_up_suggestions=draft.follow_up_suggestions,
            ensure_result_table=(agent_failed or exploration_failed or draft.fallback_requested),
        )
        evidence = self.evidence_builder.build(
            analysis_plan=state["analysis_plan"],
            query_plan=state["query_plan"],
            compiled_queries=state["compiled_queries"],
            executions=state["execution_records"],
            bundle=state["dataset_bundle"],
            analytics_tool_results=analytics_tool_results,
            metric_definitions=self.metric_definitions,
            semantic_package_version=self.semantic_package_version,
        )
        visualization_requirement_failed = any(
            item.rows for item in state["dataset_bundle"].datasets
        ) and not self._has_chart_preview(previews)
        partial = (
            agent_failed
            or exploration_failed
            or draft.fallback_requested
            or bool(grounding_failures)
            or bool(completeness_errors)
            or visualization_requirement_failed
            or not state["dataset_bundle"].complete
        )
        status = AnswerStatus.PARTIAL if partial else AnswerStatus.ANSWERED
        warnings = tuple(
            dict.fromkeys(
                [*state["dataset_bundle"].warnings]
                + [item.message for item in grounding_failures]
                + list(completeness_errors)
                + list(preference_notes)
                + list(visual_warnings)
                + list(analytics_warnings)
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
            "overall_claim_ids": overall_claim_ids,
            "kpi_selection_ids": [item.selection_id for item in draft.kpi_selections],
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
            feature_summaries=analysis_feature_summaries,
            analytics_tool_results=analytics_tool_results,
            dashboard_spec=dashboard,
            visualization_previews=previews,
            claims=claims,
            overall_claim_ids=overall_claim_ids,
            kpi_selections=() if agent_failed else draft.kpi_selections,
            evidence_package=evidence,
            limitations=analytical_limitations,
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
        *,
        feature_summaries: tuple[FeatureSummary, ...],
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
                    feature_summaries=feature_summaries,
                    visualization_previews=previews,
                    attempt=attempt,
                    correlation_id=state["correlation_id"],
                    fixture_id=state.get("fixture_id"),
                )
            except Exception:
                break
            current_draft = candidate
            current_grounding = self.grounder.ground(
                current_draft.claims,
                state["dataset_bundle"],
                feature_summaries=feature_summaries,
            )
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
        overall_claim_ids = list(draft.overall_claim_ids)
        for claim_id in sorted(
            {item for item in overall_claim_ids if overall_claim_ids.count(item) > 1}
        ):
            errors.append(f"summary:DUPLICATE_CLAIM_ID:{claim_id}")
        unknown_overall_claims = set(overall_claim_ids) - declared_claim_ids
        if unknown_overall_claims:
            errors.append(f"summary:UNKNOWN_CLAIM:{','.join(sorted(unknown_overall_claims))}")
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
        chart_preview_ids = {
            item.object_id for item in previews if Phase5Nodes._is_chart_preview(item)
        }
        selected_chart_preview_ids = {
            item.preview_id
            for item in draft.visual_insights
            if item.preview_id in chart_preview_ids
        }
        if (
            any(item.rows for item in state["dataset_bundle"].datasets)
            and chart_preview_ids
            and not selected_chart_preview_ids
        ):
            errors.append("visualization:MISSING_CHART_INTERPRETATION")
        selection_ids = [item.selection_id for item in draft.kpi_selections]
        for selection_id in sorted(
            {item for item in selection_ids if selection_ids.count(item) > 1}
        ):
            errors.append(f"kpi:DUPLICATE_SELECTION_ID:{selection_id}")
        datasets = {item.dataset_id: item for item in state["dataset_bundle"].datasets}
        for selection in draft.kpi_selections:
            dataset = datasets.get(selection.dataset_id)
            if dataset is None:
                errors.append(f"kpi:UNKNOWN_DATASET:{selection.selection_id}")
                continue
            unknown_tasks = set(selection.task_ids) - task_ids
            if unknown_tasks:
                errors.append(
                    "kpi:UNKNOWN_TASK_ID:"
                    f"{selection.selection_id}:{','.join(sorted(unknown_tasks))}"
                )
            column = next(
                (item for item in dataset.columns if item.name == selection.measure_column),
                None,
            )
            if (
                column is None
                or column.semantic_role not in {"metric", "measure"}
                or column.data_type not in {"integer", "number", "metric"}
            ):
                errors.append(f"kpi:INVALID_MEASURE:{selection.selection_id}")
            if dataset.grain or len(dataset.rows) != 1:
                errors.append(f"kpi:NOT_A_SCALAR_DATASET:{selection.selection_id}")
        if any(item.rows for item in state["dataset_bundle"].datasets) and not overall_claim_ids:
            errors.append("summary:MISSING_OVERALL_SYNTHESIS")
        for claim_id in overall_claim_ids:
            claim = grounded_by_id.get(claim_id)
            if claim is None:
                errors.append(f"summary:UNGROUNDED_CLAIM:{claim_id}")
        for index, claim in enumerate(grounding.claims):
            unknown = set(claim.task_ids) - task_ids
            if unknown:
                errors.append(f"{index}:UNKNOWN_TASK_ID:{','.join(sorted(unknown))}")
        summary_covered = {
            task_id
            for claim in Phase5Nodes._claims_for_ids(grounding.claims, tuple(overall_claim_ids))
            for task_id in claim.task_ids
            if task_id in task_ids
        }
        explicitly_limited = {
            task_id
            for task_id in required
            if any(task_id in limitation for limitation in draft.limitations)
        }
        for task_id in sorted(required - summary_covered - explicitly_limited):
            errors.append(f"summary:MISSING_REQUIRED_TASK:{task_id}")
        summary_claims = Phase5Nodes._claims_for_ids(grounding.claims, tuple(overall_claim_ids))
        if (
            any(item.rows for item in state["dataset_bundle"].datasets)
            and summary_claims
            and not any(item.importance == "primary" for item in summary_claims)
        ):
            errors.append("summary:MISSING_PRIMARY_CLAIM")
        return tuple(errors)

    @staticmethod
    def _claims_for_ids(
        claims: tuple[ClaimSpec, ...],
        claim_ids: tuple[str, ...],
    ) -> tuple[ClaimSpec, ...]:
        by_id = {item.source_claim_id: item for item in claims if item.source_claim_id is not None}
        return tuple(by_id[item] for item in claim_ids if item in by_id)

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
            tasks=analysis.tasks,
            filter_summary=tuple(
                f"{item.field_id}:{item.operator}:{','.join(map(str, item.values))}"
                for item in analysis.scope.filters
            ),
            time_summary=(
                f"[{analysis.scope.time_range.from_inclusive.isoformat()},"
                f"{analysis.scope.time_range.to_exclusive.isoformat()})"
            ),
        )
