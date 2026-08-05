"""Deterministic field, metric, value, and policy resolution."""

from datetime import UTC, datetime

from app.contracts.analysis import (
    AnalysisPlan,
    ResolvedAnalysis,
    ResolvedEntityMember,
    ResolvedFieldDescriptor,
    ResolvedFilter,
    ResolvedMeasure,
    ResolvedMetric,
)
from app.contracts.common import Provenance, semantic_hash
from app.contracts.metric import AggregationKind, FormulaNode, MeasureDefinition, MetricDefinition
from app.contracts.semantic import CanonicalField, EntityDefinition
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


class MeasureResolver:
    def __init__(self, measures: tuple[MeasureDefinition, ...]) -> None:
        self.by_id = {measure.versioned_id: measure for measure in measures}

    def require(self, measure_id: str) -> MeasureDefinition:
        measure = self.by_id.get(measure_id)
        if measure is None:
            raise SemanticResolutionError(f"unknown measure_id: {measure_id}")
        return measure


class MemberResolver:
    """Resolve configured members without exposing a high-cardinality field to an LLM."""

    def __init__(self, entities: tuple[EntityDefinition, ...]) -> None:
        self.by_id = {entity.versioned_id: entity for entity in entities}

    def resolve(self, entity_id: str, mention: str) -> ResolvedEntityMember:
        entity = self.by_id.get(entity_id)
        if entity is None or not entity.enabled:
            raise SemanticResolutionError(f"unknown entity_id: {entity_id}")
        normalized = mention.casefold().strip()
        if len(normalized) < entity.minimum_query_length:
            raise SemanticResolutionError("entity mention is too short for safe resolution")
        if entity.member_resolution == "dictionary":
            matches = [
                member_id
                for member_id, aliases in entity.dictionary.items()
                if normalized == member_id.casefold()
                or normalized in {alias.casefold() for alias in aliases}
            ]
            if len(matches) != 1:
                raise SemanticResolutionError(
                    "entity member is ambiguous or absent; clarification is required"
                )
            member_id = matches[0]
        elif entity.member_resolution == "exact":
            member_id = mention.strip()
        else:
            raise SemanticResolutionError(
                "gateway member lookup requires the approved runtime member adapter"
            )
        return ResolvedEntityMember(
            entity_id=entity.versioned_id,
            mention=mention,
            member_id=member_id,
            resolution=entity.member_resolution,
        )


class AnalysisPlanResolver:
    """Bind only validated IDs to authoritative package objects."""

    def __init__(self, package: CompiledSemanticPackage) -> None:
        self.package = package
        self.fields = FieldResolver(package.fields())
        self.metrics = MetricResolver(package.metrics())
        self.measures = MeasureResolver(package.measures())
        self.members = MemberResolver(package.entities())
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

        active_decisions = {
            item.metric_id: item
            for item in plan.metric_decisions
            if item.decision in {"required", "recommended", "optional"}
        }
        resolved_metrics: list[ResolvedMetric] = []
        for decision in active_decisions.values():
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

        resolved_measures: list[ResolvedMeasure] = []
        for measure_decision in plan.measure_decisions:
            if measure_decision.decision not in {"required", "recommended", "optional"}:
                continue
            measure = self.measures.require(measure_decision.measure_id)
            try:
                aggregation = AggregationKind(
                    measure_decision.aggregation or measure.default_aggregation
                )
            except ValueError as error:
                raise SemanticResolutionError("unsupported aggregation selection") from error
            executable = measure.enabled and aggregation in measure.allowed_aggregations
            measure_reason: str | None = None
            if measure.source_field_id is not None:
                capability = f"aggregate_{aggregation.value}"
                try:
                    field = self.fields.require(measure.source_field_id, capability=capability)
                    if field.field_id in policy.blocked_field_ids:
                        raise SemanticResolutionError(f"field is blocked: {field.field_id}")
                    resolved_field_ids.add(field.field_id)
                except SemanticResolutionError as error:
                    executable = False
                    measure_reason = str(error)
            resolved_measures.append(
                ResolvedMeasure(
                    measure_id=measure.measure_id,
                    version=measure.version,
                    source_field_id=measure.source_field_id,
                    aggregation=aggregation.value,
                    parameters=measure.default_parameters,
                    unit=measure.unit,
                    semantics=measure.semantics.value,
                    approximate=measure.approximate or aggregation == AggregationKind.CARDINALITY,
                    executable=executable,
                    reason=measure_reason,
                )
            )

        resolved_entities = tuple(
            self.members.resolve(reference.entity_id, reference.mention)
            for reference in plan.entity_references
        )

        answerable = (
            bool(resolved_metrics or resolved_measures)
            and all(item.executable for item in resolved_metrics)
            and all(item.executable for item in resolved_measures)
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
            "measures": [measure.model_dump(mode="json") for measure in resolved_measures],
            "entities": [entity.model_dump(mode="json") for entity in resolved_entities],
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
            measures=tuple(resolved_measures),
            entities=resolved_entities,
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
