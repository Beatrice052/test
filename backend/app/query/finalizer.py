"""Promote an Agent B draft into an authoritative, budgeted QueryPlan."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import ceil

from app.contracts.analysis import AnalysisPlan, ResolvedAnalysis
from app.contracts.common import Provenance, semantic_hash
from app.contracts.query import QueryPlan, QueryPlanDraft, QueryStep
from app.persistence.ids import new_id
from app.query.consolidator import QueryConsolidator
from app.query.cost import QueryBudget
from app.query.index_router import IndexRouter


class QueryPlanFinalizationError(ValueError):
    pass


class QueryPlanFinalizer:
    def __init__(self, *, index_router: IndexRouter, budget: QueryBudget) -> None:
        self.index_router = index_router
        self.budget = budget
        self.consolidator = QueryConsolidator()

    def finalize(
        self,
        draft: QueryPlanDraft,
        analysis: AnalysisPlan,
        resolved: ResolvedAnalysis,
    ) -> QueryPlan:
        if draft.analysis_plan_id != analysis.object_id or draft.analysis_plan_id != (
            resolved.analysis_plan_id
        ):
            raise QueryPlanFinalizationError("analysis plan identity mismatch")
        if not draft.steps:
            raise QueryPlanFinalizationError("query plan has no steps")
        steps = self.consolidator.consolidate(draft.steps)
        if len({step.step_id for step in steps}) != len(steps):
            raise QueryPlanFinalizationError("query step IDs are not unique")
        self._validate_dependencies(steps)
        if not any(step.required for step in steps):
            raise QueryPlanFinalizationError("query plan must contain a required base step")
        covered_tasks = {task_id for step in steps for task_id in step.purpose_task_ids}
        missing_required_tasks = {
            task.task_id
            for task in analysis.tasks
            if task.priority == "required" and task.task_id not in covered_tasks
        }
        if missing_required_tasks:
            raise QueryPlanFinalizationError(
                f"required analytical tasks are not covered: {sorted(missing_required_tasks)}"
            )
        self._validate_required_task_sufficiency(steps, analysis)
        steps = self._apply_profiled_bucket_bounds(steps, analysis, resolved)
        finalized: list[QueryStep] = []
        notes = list(draft.consolidation_notes)
        for step in steps:
            finalized_step, route_notes = self._finalize_step(step, analysis, resolved)
            finalized.append(finalized_step)
            notes.extend(route_notes)
        total_buckets = sum(step.estimated_buckets for step in finalized)
        effective_bucket_limit = min(self.budget.max_total_buckets, analysis.budget.max_buckets)
        if total_buckets > effective_bucket_limit:
            raise QueryPlanFinalizationError("total estimated buckets exceed effective budget")
        self.budget.validate(
            query_count=len(finalized),
            total_buckets=total_buckets,
            timeout_ms=max(step.timeout_ms for step in finalized),
        )
        payload = {
            "analysis_plan_id": analysis.object_id,
            "steps": [step.model_dump(mode="json") for step in finalized],
            "reuse_strategy": draft.reuse_strategy,
            "consolidation_notes": notes,
            "total_estimated_buckets": total_buckets,
        }
        content_hash = semantic_hash(payload)
        return QueryPlan(
            object_id=new_id("qp"),
            created_at=datetime.now(UTC),
            content_hash=content_hash,
            provenance=Provenance(
                producer="query.plan_finalizer",
                source_ids=(analysis.object_id, resolved.object_id),
            ),
            analysis_plan_id=analysis.object_id,
            steps=tuple(finalized),
            reuse_strategy=draft.reuse_strategy,
            consolidation_notes=tuple(dict.fromkeys(notes)),
            total_estimated_buckets=total_buckets,
        )

    def _finalize_step(
        self,
        step: QueryStep,
        analysis: AnalysisPlan,
        resolved: ResolvedAnalysis,
    ) -> tuple[QueryStep, tuple[str, ...]]:
        if step.dataset_id not in resolved.dataset_ids:
            raise QueryPlanFinalizationError(f"unresolved dataset: {step.dataset_id}")
        if step.time_range != resolved.time_range or step.time_range != analysis.scope.time_range:
            raise QueryPlanFinalizationError("QueryPlan time range differs from AnalysisPlan")
        if step.time_field_id != resolved.time_field_id:
            raise QueryPlanFinalizationError("QueryPlan changed the resolved time field")
        if not set(step.index_patterns).issubset(resolved.index_patterns):
            raise QueryPlanFinalizationError("draft contains a non-candidate index")
        allowed_fields = set(resolved.resolved_field_ids)
        referenced_fields = {
            step.time_field_id,
            *step.dimensions,
            *(item.field_id for item in step.filters),
        }
        if not referenced_fields.issubset(allowed_fields):
            raise QueryPlanFinalizationError(
                f"step references unresolved fields: {sorted(referenced_fields - allowed_fields)}"
            )
        allowed_metrics = {f"{item.metric_id}.{item.version}" for item in resolved.metrics}
        if not set(step.measures).issubset(allowed_metrics):
            unresolved_metrics = sorted(set(step.measures) - allowed_metrics)
            raise QueryPlanFinalizationError(
                f"step references unresolved metrics: {unresolved_metrics}"
            )
        resolved_metrics = {f"{item.metric_id}.{item.version}": item for item in resolved.metrics}
        for metric_id in step.measures:
            metric = resolved_metrics[metric_id]
            missing_metric_dimensions = set(metric.required_field_ids) - set(step.dimensions)
            if missing_metric_dimensions:
                raise QueryPlanFinalizationError(
                    "metric-required aggregation dimensions were dropped: "
                    f"{sorted(missing_metric_dimensions)}"
                )
        expected_filters = {
            (item.field_id, item.operator, item.values) for item in resolved.filters
        }
        actual_filters = {(item.field_id, item.operator, item.values) for item in step.filters}
        if not expected_filters.issubset(actual_filters):
            raise QueryPlanFinalizationError("mandatory resolved filter was dropped")
        task_ids = {task.task_id for task in analysis.tasks}
        if not set(step.purpose_task_ids).issubset(task_ids):
            raise QueryPlanFinalizationError("step references an unknown analytical task")

        metric_required_fields = tuple(
            dict.fromkeys(
                field_id
                for metric in resolved.metrics
                if f"{metric.metric_id}.{metric.version}" in step.measures
                for field_id in metric.required_field_ids
            )
        )
        required_fields = tuple(
            dict.fromkeys(
                (
                    step.time_field_id,
                    *step.dimensions,
                    *(item.field_id for item in step.filters),
                    *metric_required_fields,
                )
            )
        )
        route = self.index_router.route(
            dataset_id=step.dataset_id,
            time_range=step.time_range,
            policy_id=resolved.policy_scope_id,
            available_indices=resolved.index_patterns,
            required_field_ids=required_fields,
        )
        if not route.indices:
            raise QueryPlanFinalizationError("no compatible routed index remains")
        notes: list[str] = []
        if route.missing_indices:
            notes.append(f"missing indices omitted: {','.join(route.missing_indices)}")
        if route.incompatible_indices:
            notes.append(
                f"mapping-incompatible indices omitted: {','.join(route.incompatible_indices)}"
            )
        return step.model_copy(update={"index_patterns": route.indices}), tuple(notes)

    @staticmethod
    def _validate_required_task_sufficiency(
        steps: tuple[QueryStep, ...], analysis: AnalysisPlan
    ) -> None:
        """A purpose label cannot pretend that a step fetched the task's required grain."""

        for task in analysis.tasks:
            if task.priority != "required":
                continue
            supporting = tuple(
                step for step in steps if step.required and task.task_id in step.purpose_task_ids
            )
            if not supporting:
                raise QueryPlanFinalizationError(
                    f"required analytical task has no required query step: {task.task_id}"
                )
            sufficiently_scoped = any(
                set(task.dimension_ids).issubset(step.dimensions)
                and set(task.metric_ids).issubset(step.measures)
                and set(task.grain).issubset(step.grain)
                for step in supporting
            )
            if not sufficiently_scoped:
                raise QueryPlanFinalizationError(
                    f"required analytical task is not fetched at a sufficient grain: {task.task_id}"
                )

    @classmethod
    def _apply_profiled_bucket_bounds(
        cls,
        steps: tuple[QueryStep, ...],
        analysis: AnalysisPlan,
        resolved: ResolvedAnalysis,
    ) -> tuple[QueryStep, ...]:
        descriptors = {item.field_id: item for item in resolved.field_descriptors}
        top_n_sources = {
            binding.source_dataset_contract
            for step in steps
            for binding in step.parameter_bindings
            if binding.selection == "top_n"
        }
        adjusted: list[QueryStep] = []
        for step in steps:
            if step.result_contract_id in top_n_sources:
                adjusted.append(step)
                continue
            projected = 1
            has_profile = False
            for field_id in step.dimensions:
                descriptor = descriptors.get(field_id)
                if descriptor is None:
                    continue
                cardinality = descriptor.cardinality_estimate
                if descriptor.semantic_type == "time_dimension":
                    cardinality = cls._time_bucket_count(step)
                if cardinality is None:
                    continue
                has_profile = True
                projected *= max(1, cardinality)
                if projected > analysis.budget.max_buckets:
                    break
            if not has_profile:
                adjusted.append(step)
                continue
            if projected > analysis.budget.max_buckets:
                raise QueryPlanFinalizationError(
                    "profiled dimension cardinality exceeds the query bucket budget"
                )
            adjusted.append(
                step.model_copy(
                    update={"estimated_buckets": max(step.estimated_buckets, projected)}
                )
            )
        return tuple(adjusted)

    @staticmethod
    def _time_bucket_count(step: QueryStep) -> int | None:
        grain = next((item for item in step.grain if item in {"day", "week", "month"}), None)
        if grain is None:
            return None
        start = step.time_range.from_inclusive
        end = step.time_range.to_exclusive
        seconds = (end - start).total_seconds()
        if grain == "day":
            return max(1, ceil(seconds / 86_400))
        if grain == "week":
            return max(1, ceil(seconds / (7 * 86_400)))
        last = end - timedelta(microseconds=1)
        return max(1, (last.year - start.year) * 12 + last.month - start.month + 1)

    def _validate_dependencies(self, steps: tuple[QueryStep, ...]) -> None:
        known: dict[str, QueryStep] = {}
        depths: dict[str, int] = {}
        for step in steps:
            if not set(step.depends_on).issubset(known):
                raise QueryPlanFinalizationError(
                    "dependency is missing or not topologically ordered"
                )
            if step.parameter_bindings and not step.depends_on:
                raise QueryPlanFinalizationError("parameter binding has no dependency")
            dependency_contracts = {
                known[dependency_id].result_contract_id for dependency_id in step.depends_on
            }
            for binding in step.parameter_bindings:
                if binding.source_dataset_contract not in dependency_contracts:
                    raise QueryPlanFinalizationError(
                        "parameter binding source is not a declared dependency result"
                    )
            depth = (
                max(depths[dependency_id] for dependency_id in step.depends_on) + 1
                if step.depends_on
                else 0
            )
            if depth > self.budget.max_dependent_query_rounds:
                raise QueryPlanFinalizationError("dependent query rounds exceed policy")
            known[step.step_id] = step
            depths[step.step_id] = depth
