"""Deterministic field, metric, value, and policy resolution."""

from datetime import UTC, datetime

from app.contracts.analysis import (
    AnalysisPlan,
    ResolvedAnalysis,
    ResolvedFieldDescriptor,
    ResolvedFilter,
    ResolvedMetric,
)
from app.contracts.common import Provenance, semantic_hash
from app.contracts.metric import FormulaNode, MetricDefinition
from app.contracts.semantic import CanonicalField
from app.persistence.ids import new_id
from app.semantic.package import CompiledSemanticPackage


class SemanticResolutionError(ValueError):
    pass


class FieldResolver:
    def __init__(self, fields: tuple[CanonicalField, ...]) -> None:
        self.by_id = {field.field_id: field for field in fields}

    def require(self, field_id: str, *, capability: str | None = None) -> CanonicalField:
        field = self.by_id.get(field_id)
        if field is None:
            raise SemanticResolutionError(f"unknown field_id: {field_id}")
        if capability is not None and capability not in field.capabilities:
            raise SemanticResolutionError(
                f"field {field_id} does not support required capability: {capability}"
            )
        return field


class MetricResolver:
    def __init__(self, metrics: tuple[MetricDefinition, ...]) -> None:
        self.by_id = {metric.versioned_id: metric for metric in metrics}

    def require(self, metric_id: str) -> MetricDefinition:
        metric = self.by_id.get(metric_id)
        if metric is None:
            raise SemanticResolutionError(f"unknown metric_id: {metric_id}")
        return metric


class AnalysisPlanResolver:
    """Bind only validated IDs to authoritative package objects."""

    def __init__(self, package: CompiledSemanticPackage) -> None:
        self.package = package
        self.fields = FieldResolver(package.fields())
        self.metrics = MetricResolver(package.metrics())
        self.datasets = {dataset.dataset_id: dataset for dataset in package.datasets()}
        self.values = package.values()
        self.policies = package.policies()

    def resolve(self, plan: AnalysisPlan) -> ResolvedAnalysis:
        datasets = []
        for dataset_id in plan.scope.dataset_ids:
            dataset = self.datasets.get(dataset_id)
            if dataset is None:
                raise SemanticResolutionError(f"unknown dataset_id: {dataset_id}")
            datasets.append(dataset)
        policy = next(
            (
                item
                for item in self.policies
                if set(plan.scope.dataset_ids).issubset(item.allowed_dataset_ids)
            ),
            None,
        )
        if policy is None:
            raise SemanticResolutionError("no policy permits all requested datasets")

        resolved_field_ids: set[str] = set()
        resolved_filters: list[ResolvedFilter] = []
        for item in plan.scope.filters:
            field = self.fields.require(item.field_id, capability="filter")
            if field.field_id in policy.blocked_field_ids:
                raise SemanticResolutionError(f"field is blocked by policy: {field.field_id}")
            resolved_field_ids.add(field.field_id)
            resolved_filters.append(
                ResolvedFilter(
                    field_id=field.field_id,
                    physical_path=field.physical_path,
                    operator=item.operator,
                    values=item.values,
                )
            )
        for task in plan.tasks:
            for field_id in task.dimension_ids:
                field = self.fields.require(field_id, capability="group_by")
                if field.field_id in policy.blocked_field_ids:
                    raise SemanticResolutionError(f"field is blocked by policy: {field.field_id}")
                resolved_field_ids.add(field.field_id)

        time_field_ids = {dataset.primary_time_field_id for dataset in datasets}
        if len(time_field_ids) != 1:
            raise SemanticResolutionError("datasets do not share one primary time field")
        time_field_id = next(iter(time_field_ids))
        self.fields.require(time_field_id, capability="range")
        resolved_field_ids.add(time_field_id)

        resolved_metrics: list[ResolvedMetric] = []
        for decision in plan.metric_decisions:
            if decision.decision == "rejected":
                continue
            metric = self.metrics.require(decision.metric_id)
            required_field_ids = self._metric_required_fields(metric)
            executable = metric.enabled
            reason: str | None = None
            for field_id in required_field_ids:
                try:
                    field = self.fields.require(field_id)
                except SemanticResolutionError as error:
                    executable = False
                    reason = str(error)
                    break
                if field.field_id in policy.blocked_field_ids:
                    executable = False
                    reason = f"required field is blocked: {field.field_id}"
                    break
                resolved_field_ids.add(field.field_id)
            resolved_metrics.append(
                ResolvedMetric(
                    metric_id=metric.metric_id,
                    version=metric.version,
                    required_field_ids=required_field_ids,
                    required_grain=metric.dimensions,
                    executable=executable,
                    reason=reason,
                )
            )

        answerable = bool(resolved_metrics) and all(
            metric.executable for metric in resolved_metrics
        )
        index_patterns = tuple(
            pattern
            for pattern in policy.allowed_index_patterns
            if any(
                self._matches_dataset_prefix(pattern, dataset.index_pattern) for dataset in datasets
            )
        )
        if not index_patterns:
            answerable = False
        field_descriptors = tuple(
            self._field_descriptor(self.fields.require(field_id))
            for field_id in sorted(resolved_field_ids)
        )
        payload = {
            "analysis_plan_id": plan.object_id,
            "datasets": plan.scope.dataset_ids,
            "fields": sorted(resolved_field_ids),
            "field_descriptors": [
                descriptor.model_dump(mode="json") for descriptor in field_descriptors
            ],
            "metrics": [metric.model_dump(mode="json") for metric in resolved_metrics],
            "filters": [item.model_dump(mode="json") for item in resolved_filters],
            "package_version": self.package.manifest.package_version,
            "policy": policy.policy_id,
        }
        content_hash = semantic_hash(payload)
        return ResolvedAnalysis(
            object_id=new_id("ra"),
            created_at=datetime.now(UTC),
            content_hash=content_hash,
            provenance=Provenance(
                producer="semantic.analysis_resolver",
                source_ids=(plan.object_id, self.package.manifest.object_id),
            ),
            analysis_plan_id=plan.object_id,
            dataset_ids=plan.scope.dataset_ids,
            index_patterns=index_patterns,
            resolved_field_ids=tuple(sorted(resolved_field_ids)),
            field_descriptors=field_descriptors,
            metrics=tuple(resolved_metrics),
            filters=tuple(resolved_filters),
            time_field_id=time_field_id,
            time_range=plan.scope.time_range,
            policy_scope_id=policy.policy_id,
            method_ids=tuple(
                dict.fromkeys(
                    method for task in plan.tasks for method in task.statistical_method_ids
                )
            ),
            answerable=answerable,
            caveats=() if answerable else ("当前语义能力不足以执行全部必需指标",),
        )

    @staticmethod
    def _field_descriptor(field: CanonicalField) -> ResolvedFieldDescriptor:
        return ResolvedFieldDescriptor(
            field_id=field.field_id,
            dataset_id=field.dataset_id,
            display_name=field.display_name,
            description=field.description,
            aliases=field.aliases,
            business_domain=field.business_domain,
            mapping_type=field.mapping_type,
            semantic_type=field.semantic_type,
            maturity=field.maturity,
            capabilities=field.capabilities,
            compatibility=field.compatibility,
            cardinality_estimate=field.cardinality.estimate,
            cardinality_approximate=field.cardinality.approximate,
        )

    def _metric_required_fields(self, metric: MetricDefinition) -> tuple[str, ...]:
        status_needed = any(
            self._contains_filtered_count(node)
            for node in (metric.numerator, metric.denominator, metric.formula)
            if node is not None
        )
        if not status_needed:
            return ()
        sources = tuple(
            dictionary.source_field_id
            for dictionary in self.values
            if {"success", "failure"}.intersection(dictionary.values.values())
        )
        return tuple(dict.fromkeys(sources))

    @classmethod
    def _contains_filtered_count(cls, node: FormulaNode) -> bool:
        return node.operator == "filtered_count" or any(
            cls._contains_filtered_count(child) for child in node.operands
        )

    @staticmethod
    def _matches_dataset_prefix(index_name: str, index_pattern: str) -> bool:
        prefix = index_pattern.split("{", 1)[0]
        return index_name.startswith(prefix)
