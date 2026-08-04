"""One-query deterministic Result → Dataset → Metric → QA → Feature pipeline."""

from dataclasses import dataclass

from app.analytics.bundle import DatasetBundleBuilder
from app.analytics.contract_factory import DatasetContractFactory
from app.analytics.derivation import StatusMetricDeriver
from app.analytics.features import FeatureSummaryBlocked, FeatureSummaryBuilder
from app.analytics.normalizer import ResultNormalizer
from app.analytics.parser import RawResultParser
from app.analytics.qa import DataQAEngine
from app.analytics.rollup import AdditiveRollupDeriver
from app.analytics.statistics import StatisticEngine
from app.contracts.common import JsonValue
from app.contracts.dataset import (
    DataQARecord,
    DatasetBundle,
    DatasetColumn,
    ReconciliationRecord,
    TabularDataset,
)
from app.contracts.execution import ExecutionRecord, RawSearchResult
from app.contracts.insight import FeatureSummary, StatisticalResult
from app.contracts.metric import MethodDefinition, MetricDefinition, ValueDictionary
from app.contracts.query import CompiledQuery
from app.contracts.semantic import CanonicalField


@dataclass(frozen=True, slots=True)
class AnalyticsPipelineResult:
    bundle: DatasetBundle
    feature_summaries: tuple[FeatureSummary, ...]
    fatal: bool


class AnalyticsPipeline:
    def __init__(
        self,
        *,
        metric_definitions: tuple[MetricDefinition, ...],
        value_dictionaries: tuple[ValueDictionary, ...],
        method_definitions: tuple[MethodDefinition, ...] = (),
        fields: tuple[CanonicalField, ...] = (),
    ) -> None:
        self.metrics = {item.versioned_id: item for item in metric_definitions}
        self.methods = {item.method_id: item for item in method_definitions}
        self.value_dictionaries = value_dictionaries
        self.parser = RawResultParser()
        self.contract_factory = DatasetContractFactory(fields)
        self.normalizer = ResultNormalizer()
        self.deriver = StatusMetricDeriver()
        self.rollups = AdditiveRollupDeriver()
        self.qa = DataQAEngine()
        self.statistics = StatisticEngine()
        self.features = FeatureSummaryBuilder()
        self.bundles = DatasetBundleBuilder()

    def process(
        self,
        query: CompiledQuery,
        raw: RawSearchResult,
        executions: tuple[ExecutionRecord, ...],
        *,
        method_ids: tuple[str, ...] = (),
    ) -> AnalyticsPipelineResult:
        parsed = self.parser.parse(query, raw)
        contract = self.contract_factory.build(query)
        base = self.normalizer.normalize(parsed, contract)
        base_qa = self.qa.evaluate(
            base,
            contract=contract,
            executions=executions,
            time_range=query.semantics.time_range,
        )
        datasets: list[TabularDataset] = [base]
        all_qa: list[DataQARecord] = list(base_qa)
        reconciliation: tuple[ReconciliationRecord, ...] = ()
        feature_targets: list[TabularDataset] = [base]
        metric_values_by_row = {}
        requested_metrics = tuple(
            self.metrics[item] for item in query.semantics.metric_ids if item in self.metrics
        )
        if requested_metrics and not self.qa.has_fatal(base_qa):
            status_dictionary = self._status_dictionary(query)
            requires_status = any(
                item.numerator is not None or item.denominator is not None
                for item in requested_metrics
            )
            if requires_status and status_dictionary is None:
                missing = DataQARecord(
                    rule_id="qa_dimension_present",
                    severity="FATAL",
                    passed=False,
                    message="ratio metric requires a registered status dimension",
                    dataset_id=base.dataset_id,
                )
                all_qa.append(missing)
            else:
                status_field_id = (
                    status_dictionary.source_field_id if status_dictionary is not None else None
                )
                group_by = tuple(item for item in contract.dimensions if item != status_field_id)
                dictionary = status_dictionary or self._empty_dictionary()
                metric_views = self._metric_view_grains(
                    query,
                    contract.columns,
                    group_by,
                )
                for suffix, view_grain in metric_views:
                    output_dataset_id = (
                        f"{query.step_id}_metrics"
                        if suffix == "primary"
                        else f"{query.step_id}_{suffix}_metrics"
                    )
                    derivation_id = f"derive_{output_dataset_id}.v1"
                    derived = self.deriver.derive(
                        base,
                        output_dataset_id=output_dataset_id,
                        derivation_id=derivation_id,
                        group_by=view_grain,
                        status_field_id=status_field_id,
                        value_dictionary=dictionary,
                        metric_definitions=requested_metrics,
                    )
                    reproduced = self.deriver.derive(
                        base,
                        output_dataset_id=output_dataset_id,
                        derivation_id=derivation_id,
                        group_by=view_grain,
                        status_field_id=status_field_id,
                        value_dictionary=dictionary,
                        metric_definitions=requested_metrics,
                    )
                    derived_qa = self.qa.evaluate(
                        derived.dataset,
                        metric_values_by_row=derived.metric_values_by_row,
                        reconciliation=derived.reconciliation,
                        rederived_content_hash=reproduced.dataset.content_hash,
                    )
                    datasets.append(derived.dataset)
                    all_qa.extend(derived_qa)
                    reconciliation = (*reconciliation, *derived.reconciliation)
                    feature_targets.append(derived.dataset)
                    metric_values_by_row.update(derived.metric_values_by_row)

                for suffix, view_grain in self._composition_view_grains(
                    contract.columns, contract.dimensions, status_field_id
                ):
                    rollup, rollup_reconciliation = self.rollups.derive(
                        base,
                        output_dataset_id=f"{query.step_id}_{suffix}",
                        group_by=view_grain,
                    )
                    datasets.append(rollup)
                    reconciliation = (*reconciliation, rollup_reconciliation)
                    feature_targets.append(rollup)
        del metric_values_by_row
        fatal = self.qa.has_fatal(all_qa)
        summaries: tuple[FeatureSummary, ...] = ()
        if not fatal:
            try:
                summaries = tuple(
                    self.features.build(
                        target,
                        statistical_results=self._statistics_for(target, method_ids),
                        qa_records=tuple(all_qa),
                    )
                    for target in feature_targets
                )
            except FeatureSummaryBlocked:
                fatal = True
        bundle = self.bundles.build(
            tuple(datasets),
            data_qa=tuple(all_qa),
            reconciliation=reconciliation,
        )
        return AnalyticsPipelineResult(bundle=bundle, feature_summaries=summaries, fatal=fatal)

    def _status_dictionary(self, query: CompiledQuery) -> ValueDictionary | None:
        dimensions = {item.dimension_id for item in query.semantics.bucket_path}
        return next(
            (item for item in self.value_dictionaries if item.source_field_id in dimensions),
            None,
        )

    @staticmethod
    def _metric_view_grains(
        query: CompiledQuery,
        columns: tuple[DatasetColumn, ...],
        primary: tuple[str, ...],
    ) -> tuple[tuple[str, tuple[str, ...]], ...]:
        semantic_types = {item.name: item.semantic_type for item in columns}
        time_fields = tuple(
            item
            for item in primary
            if item == query.semantics.time_field_id or semantic_types.get(item) == "time_dimension"
        )
        category_fields = tuple(item for item in primary if item not in time_fields)
        candidates: list[tuple[str, tuple[str, ...]]] = [("primary", primary), ("overall", ())]
        candidates.extend(
            (f"dimension_{index}", (field_id,)) for index, field_id in enumerate(primary, start=1)
        )
        candidates.extend(
            (f"time_category_{index}", (time_field, category_field))
            for index, (time_field, category_field) in enumerate(
                (
                    (time_field, category_field)
                    for time_field in time_fields
                    for category_field in category_fields
                ),
                start=1,
            )
        )
        unique: list[tuple[str, tuple[str, ...]]] = []
        seen: set[tuple[str, ...]] = set()
        for suffix, grain in candidates:
            if grain in seen:
                continue
            seen.add(grain)
            unique.append((suffix, grain))
        return tuple(unique)

    @staticmethod
    def _composition_view_grains(
        columns: tuple[DatasetColumn, ...],
        dimensions: tuple[str, ...],
        status_field_id: str | None,
    ) -> tuple[tuple[str, tuple[str, ...]], ...]:
        if status_field_id is None or status_field_id not in dimensions:
            return ()
        semantic_types = {item.name: item.semantic_type for item in columns}
        eligible = tuple(
            item
            for item in dimensions
            if item != status_field_id
            and semantic_types.get(item) in {"categorical_dimension", "time_dimension"}
        )
        return tuple(
            (f"composition_{index}", (field_id, status_field_id))
            for index, field_id in enumerate(eligible, start=1)
        )

    def _statistics_for(
        self, dataset: TabularDataset, method_ids: tuple[str, ...]
    ) -> tuple[StatisticalResult, ...]:
        time_column = next(
            (item.name for item in dataset.columns if item.data_type == "datetime"), None
        )
        results: list[StatisticalResult] = []
        for method_id in dict.fromkeys(method_ids):
            definition = self.methods.get(method_id)
            base_params: dict[str, JsonValue] = (
                dict(definition.default_params) if definition is not None else {}
            )
            base_params.setdefault("n", 5)
            if time_column is not None:
                base_params.setdefault("time_column", time_column)
            for measure in self._analysis_measures(dataset):
                params = {**base_params, "column": measure}
                result = self.statistics.compute(method_id, dataset, params)
                if (
                    definition is not None
                    and result.applicability == "APPLICABLE"
                    and result.sample_size < definition.minimum_rows
                ):
                    result = result.model_copy(
                        update={
                            "applicability": "NOT_APPLICABLE",
                            "warnings": tuple(
                                dict.fromkeys(
                                    [
                                        *result.warnings,
                                        "registered minimum_rows was not satisfied",
                                    ]
                                )
                            ),
                        }
                    )
                results.append(result)
        return tuple(results)

    @staticmethod
    def _empty_dictionary() -> ValueDictionary:
        return ValueDictionary(
            dictionary_id="empty_status_group",
            version="v1",
            source_field_id="internal.no_status",
            values={},
            null_group="unknown",
            owner="framework",
        )

    @staticmethod
    def _analysis_measures(dataset: TabularDataset) -> tuple[str, ...]:
        numeric = tuple(
            item.name
            for item in dataset.columns
            if item.semantic_role in {"metric", "measure"}
            and item.data_type in {"integer", "number", "metric"}
        )
        governed_metrics = tuple(
            item.name for item in dataset.columns if item.semantic_role == "metric"
        )
        return governed_metrics or numeric or ("record_count",)
