"""Build immutable source/calculation/definition/claim Evidence and safe exports."""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from app.contracts.analysis import AnalysisPlan
from app.contracts.common import JsonValue, Provenance, canonical_json, semantic_hash
from app.contracts.dataset import DatasetBundle, TabularDataset
from app.contracts.evidence import (
    AdvancedEvidence,
    BusinessEvidence,
    CalculationTableEvidence,
    ClaimTraceEvidence,
    EvidenceArtifactRef,
    EvidencePackage,
    EvidenceQualitySummary,
    EvidenceRedaction,
    SourceQueryEvidence,
    TechnicalDefinitionEvidence,
)
from app.contracts.execution import ExecutionRecord, RawSearchResult
from app.contracts.insight import AnalyticsToolResult, ClaimSpec, EvidenceRef
from app.contracts.metric import (
    FormulaNode,
    MeasureDefinition,
    MethodDefinition,
    MetricDefinition,
)
from app.contracts.query import CompiledQuery, QueryPlan
from app.contracts.request import IdentityContext
from app.persistence.ids import new_id
from app.presentation.artifacts import EvidenceArtifactStore


class EvidenceBuilder:
    def __init__(self, artifact_store: EvidenceArtifactStore | None = None) -> None:
        self.artifact_store = artifact_store

    def build(
        self,
        *,
        analysis_plan: AnalysisPlan,
        query_plan: QueryPlan,
        compiled_queries: tuple[CompiledQuery, ...],
        executions: tuple[ExecutionRecord, ...],
        bundle: DatasetBundle,
        raw_results: tuple[RawSearchResult, ...] = (),
        analytics_tool_results: tuple[AnalyticsToolResult, ...] = (),
        claims: tuple[ClaimSpec, ...] = (),
        metric_definitions: tuple[MetricDefinition, ...],
        measure_definitions: tuple[MeasureDefinition, ...] = (),
        method_definitions: tuple[MethodDefinition, ...] = (),
        semantic_package_version: str,
        answer_id: str | None = None,
    ) -> EvidencePackage:
        answer_ref = answer_id or "pending"
        datasets_by_contract = {item.contract_id: item for item in bundle.datasets}
        raw_by_query = {item.query_id: item for item in raw_results}
        source_queries: list[SourceQueryEvidence] = []
        source_artifacts: list[EvidenceArtifactRef] = []
        execution_summaries: list[dict[str, JsonValue]] = []

        for query in compiled_queries:
            source = datasets_by_contract.get(query.result_contract_id)
            if source is None:
                continue
            source_table = self._dataset_artifact(source, "source_result_table")
            raw = raw_by_query.get(query.object_id)
            raw_artifact = self._raw_artifact(raw, query, answer_ref) if raw is not None else None
            if raw_artifact is not None:
                source_artifacts.append(raw_artifact)
            source_artifacts.append(source_table)
            query_executions = tuple(item for item in executions if item.step_id == query.step_id)
            raw_page_count = (
                raw.gateway_metadata.get("composite_pages", 1) if raw is not None else 1
            )
            page_count = max(
                len(query_executions),
                raw_page_count
                if isinstance(raw_page_count, int) and not isinstance(raw_page_count, bool)
                else 1,
            )
            bucket_count = self._leaf_bucket_count(raw.aggregations) if raw is not None else 0
            complete = source.complete and raw is not None and not raw.timed_out
            partial = not complete
            source_queries.append(
                SourceQueryEvidence(
                    query_id=query.object_id,
                    query_plan_id=query.query_plan_id,
                    query_step_id=query.step_id,
                    dataset_id=query.semantics.dataset_id,
                    indices=query.indices,
                    time_range=query.semantics.time_range.model_dump(mode="json"),
                    timezone=query.semantics.time_range.timezone,
                    filters=tuple(
                        item.model_dump(mode="json")
                        for step in query_plan.steps
                        if step.step_id == query.step_id
                        for item in step.filters
                    ),
                    dimensions=tuple(item.dimension_id for item in query.semantics.bucket_path),
                    grain=query.semantics.grain,
                    metrics=query.semantics.metric_ids,
                    measures=tuple(
                        item.model_dump(mode="json") for item in query.semantics.field_measures
                    ),
                    query_fingerprint=query.query_fingerprint,
                    safe_query_summary={
                        "size": 0,
                        "read_only": True,
                        "aggregation_kinds": self._aggregation_kinds(query.query_dsl),
                        "source_artifact_hash": (
                            raw_artifact.content_hash if raw_artifact is not None else None
                        ),
                    },
                    execution_ids=tuple(item.object_id for item in query_executions),
                    took_ms=raw.took_ms if raw is not None else 0,
                    page_count=page_count,
                    bucket_count=bucket_count,
                    row_count=len(source.rows),
                    complete=complete,
                    partial=partial,
                    raw_result_artifact=raw_artifact,
                    source_table_artifact=source_table,
                )
            )
            for execution in query_executions:
                summary = execution.model_dump(mode="json")
                summary.update(
                    {
                        "raw_artifact_id": (
                            raw_artifact.artifact_id if raw_artifact is not None else None
                        ),
                        "source_table_artifact_id": source_table.artifact_id,
                        "page_count": page_count,
                        "bucket_count": bucket_count,
                        "row_count": len(source.rows),
                        "complete": complete,
                        "partial": partial,
                    }
                )
                execution_summaries.append(summary)

        calculated_tables = list(self._calculation_tables(bundle))
        statistical_artifacts: list[EvidenceArtifactRef] = []
        for result in analytics_tool_results:
            artifact = self._statistical_artifact(result, answer_ref)
            if artifact is None:
                continue
            statistical_artifacts.append(artifact)
            calculated_tables.append(self._statistical_table(result, artifact))

        used_metric_ids = {
            metric_id for query in compiled_queries for metric_id in query.semantics.metric_ids
        }
        used_measure_ids = {
            item.measure_id for query in compiled_queries for item in query.semantics.field_measures
        }
        used_method_ids = {item.method_id for item in analytics_tool_results}
        technical_definitions = (
            *self._metric_technical_definitions(metric_definitions, used_metric_ids),
            *self._measure_technical_definitions(measure_definitions, used_measure_ids),
            *self._method_technical_definitions(method_definitions, used_method_ids),
        )
        definition_ids = {item.definition_id for item in technical_definitions}
        artifacts_by_table_id = {
            source.source_table_artifact.source_ids[0]: source.source_table_artifact
            for source in source_queries
            if source.source_table_artifact.source_ids
        }
        for table in calculated_tables:
            artifacts_by_table_id[table.table_id] = table.artifact
            artifacts_by_table_id[table.calculation_id] = table.artifact
        claim_trace = tuple(
            ClaimTraceEvidence(
                claim_id=claim.object_id,
                task_ids=claim.task_ids,
                text=claim.text,
                evidence_refs=tuple(
                    self._claim_reference_payload(item, artifacts_by_table_id)
                    for item in claim.evidence_refs
                ),
                definition_ids=tuple(
                    sorted(
                        {
                            definition_id
                            for ref in claim.evidence_refs
                            for definition_id in ref.definition_ids
                            if definition_id in definition_ids
                        }
                    )
                ),
            )
            for claim in claims
        )
        quality_summary = self._quality_summary(bundle)
        legacy_metric_definitions = tuple(
            self._metric_technical_payload(item)
            for item in metric_definitions
            if item.versioned_id in used_metric_ids
        )
        business = BusinessEvidence(
            scope={
                "analysis_plan_id": analysis_plan.object_id,
                "analysis_goal": analysis_plan.analysis_goal,
                "time_range": analysis_plan.scope.time_range.model_dump(mode="json"),
                "dataset_ids": list(analysis_plan.scope.dataset_ids),
                "semantic_package_version": semantic_package_version,
            },
            source_queries=tuple(source_queries),
            source_results=tuple(source_artifacts),
            calculated_tables=tuple(calculated_tables),
            technical_definitions=technical_definitions,
            claim_trace=claim_trace,
            quality_summary=quality_summary,
            metric_definitions=legacy_metric_definitions,
            data_tables=tuple(item.object_id for item in bundle.datasets),
            reconciliations=tuple(item.model_dump(mode="json") for item in bundle.reconciliation),
            quality=(),
            exploratory_analysis=tuple(
                {
                    "request_id": item.request_id,
                    "task_ids": list(item.task_ids),
                    "dataset_id": item.dataset_id,
                    "method_id": item.method_id,
                    "measure_column": item.measure_column,
                    "partition_columns": list(item.partition_columns),
                    "category_column": item.category_column,
                    "time_column": item.time_column,
                    "decision": item.decision,
                    "reason": item.reason,
                    "sample_size": item.result.sample_size,
                    "result_id": item.result.result_id,
                    "result": item.result.values,
                    "value_paths": list(item.result.value_paths),
                    "calculation_table_id": item.result.calculation_table_id,
                    "warnings": list(item.result.warnings),
                }
                for item in analytics_tool_results
            ),
            downloads=tuple(f"/api/v1/datasets/{item.object_id}/csv" for item in bundle.datasets),
        )
        all_artifacts = (
            *source_artifacts,
            *(item.artifact for item in calculated_tables),
            *statistical_artifacts,
        )
        advanced_artifacts = tuple({item.artifact_id: item for item in all_artifacts}.values())
        advanced = AdvancedEvidence(
            query_plan=query_plan.model_dump(mode="json"),
            compiled_queries=tuple(item.model_dump(mode="json") for item in compiled_queries),
            execution_summaries=tuple(execution_summaries),
            result_contracts=tuple(
                {
                    "contract_id": item.contract_id,
                    "dataset_id": item.dataset_id,
                    "grain": list(item.grain),
                    "columns": [column.model_dump(mode="json") for column in item.columns],
                    "completeness": item.completeness,
                    "content_hash": item.content_hash,
                }
                for item in bundle.datasets
            ),
            artifacts=advanced_artifacts,
        )
        redaction = EvidenceRedaction(
            removed_fields=(
                "credentials",
                "authorization_headers",
                "mcp_endpoint",
                "llm_prompt",
                "raw_documents",
                "unapproved_source_fields",
            ),
            policy_id="evidence.v2",
        )
        payload = {
            "business": business.model_dump(mode="json"),
            "advanced": advanced.model_dump(mode="json"),
            "redaction": redaction.model_dump(mode="json"),
        }
        return EvidencePackage(
            schema_version="2.0",
            object_id=new_id("ev"),
            created_at=datetime.now(UTC),
            content_hash=semantic_hash(payload),
            provenance=Provenance(
                producer="presentation.evidence_builder",
                source_ids=(analysis_plan.object_id, query_plan.object_id, bundle.object_id),
            ),
            business=business,
            advanced=advanced,
            redaction=redaction,
        )

    def _raw_artifact(
        self, raw: RawSearchResult, query: CompiledQuery, answer_id: str
    ) -> EvidenceArtifactRef | None:
        if self.artifact_store is None:
            return None
        payload = {
            "query_id": raw.query_id,
            "query_fingerprint": query.query_fingerprint,
            "took_ms": raw.took_ms,
            "timed_out": raw.timed_out,
            "shards": raw.shards.model_dump(mode="json"),
            "hits_total": raw.hits_total,
            "aggregations": raw.aggregations,
            "gateway_metadata": raw.gateway_metadata,
            "raw_size_bytes": raw.raw_size_bytes,
            "detail_hits_omitted": len(raw.hits),
        }
        artifact_id, content_hash, byte_size = self.artifact_store.write_json(payload)
        return EvidenceArtifactRef(
            artifact_id=artifact_id,
            artifact_kind="raw_opensearch_result",
            media_type="application/json",
            content_hash=content_hash,
            byte_size=byte_size,
            row_count=self._leaf_bucket_count(raw.aggregations),
            complete=not raw.timed_out and raw.shards.failed == 0,
            source_ids=(query.object_id,),
            preview={
                "aggregation_names": sorted(raw.aggregations),
                "bucket_count": self._leaf_bucket_count(raw.aggregations),
                "page_count": raw.gateway_metadata.get("composite_pages", 1),
                "after_keys": raw.gateway_metadata.get("composite_after_keys", []),
                "took_ms": raw.took_ms,
            },
            download_url=f"/api/v1/answers/{answer_id}/artifacts/{artifact_id}",
        )

    @staticmethod
    def _dataset_artifact(
        dataset: TabularDataset,
        artifact_kind: str,
    ) -> EvidenceArtifactRef:
        csv_content = EvidenceExporter().dataset_csv(dataset).encode("utf-8")
        csv_hash = f"sha256:{hashlib.sha256(csv_content).hexdigest()}"
        artifact_id = f"art_dataset_{csv_hash.removeprefix('sha256:')[:16]}"
        return EvidenceArtifactRef.model_validate(
            {
                "artifact_id": artifact_id,
                "artifact_kind": artifact_kind,
                "media_type": "text/csv",
                "content_hash": csv_hash,
                "byte_size": len(csv_content),
                "row_count": len(dataset.rows),
                "complete": dataset.complete,
                "approximate": any(item.approximate for item in dataset.columns),
                "source_ids": [dataset.object_id, *dataset.provenance.source_ids],
                "preview": {
                    "dataset_id": dataset.dataset_id,
                    "grain": list(dataset.grain),
                    "columns": [item.name for item in dataset.columns],
                    "rows": [item.model_dump(mode="json") for item in dataset.rows[:20]],
                    "preview_row_count": min(20, len(dataset.rows)),
                    "total_row_count": len(dataset.rows),
                },
                "download_url": f"/api/v1/datasets/{dataset.object_id}/csv",
            },
            strict=False,
        )

    def _calculation_tables(self, bundle: DatasetBundle) -> tuple[CalculationTableEvidence, ...]:
        tables: list[CalculationTableEvidence] = []
        for dataset in bundle.datasets:
            if dataset.kind != "derived":
                continue
            definition_ids = tuple(
                dict.fromkeys(
                    item
                    for column in dataset.columns
                    for item in (column.metric_id, column.measure_id)
                    if item is not None
                )
            )
            artifact = self._dataset_artifact(dataset, "calculation_table")
            raw_required_columns = dataset.provenance.metadata.get("required_columns", [])
            required_columns = (
                tuple(str(item) for item in raw_required_columns)
                if isinstance(raw_required_columns, list)
                else ()
            )
            raw_task_ids = dataset.provenance.metadata.get("task_ids", [])
            task_ids = (
                tuple(str(item) for item in raw_task_ids) if isinstance(raw_task_ids, list) else ()
            )
            tables.append(
                CalculationTableEvidence(
                    calculation_id=dataset.derivation_id or f"calculate_{dataset.dataset_id}",
                    table_id=dataset.object_id,
                    source_table_ids=tuple(dataset.provenance.source_ids),
                    task_ids=task_ids,
                    grain=dataset.grain,
                    input_columns=required_columns,
                    output_columns=tuple(item.name for item in dataset.columns),
                    definition_ids=definition_ids,
                    parameters=dict(dataset.provenance.metadata),
                    row_ids=tuple(item.row_id for item in dataset.rows),
                    content_hash=dataset.content_hash,
                    complete=dataset.complete,
                    approximate=artifact.approximate,
                    artifact=artifact,
                )
            )
        return tuple(tables)

    def _statistical_artifact(
        self, result: AnalyticsToolResult, answer_id: str
    ) -> EvidenceArtifactRef | None:
        if self.artifact_store is None:
            return None
        payload = result.model_dump(mode="json")
        artifact_id, content_hash, byte_size = self.artifact_store.write_json(payload)
        return EvidenceArtifactRef(
            artifact_id=artifact_id,
            artifact_kind="statistical_result",
            media_type="application/json",
            content_hash=content_hash,
            byte_size=byte_size,
            row_count=result.result.sample_size,
            complete=result.decision == "APPLICABLE",
            source_ids=(result.dataset_id, result.object_id),
            task_ids=result.task_ids,
            preview={
                "method_id": result.method_id,
                "decision": result.decision,
                "sample_size": result.result.sample_size,
                "value_paths": list(result.result.value_paths),
            },
            download_url=f"/api/v1/answers/{answer_id}/artifacts/{artifact_id}",
        )

    @staticmethod
    def _statistical_table(
        result: AnalyticsToolResult, artifact: EvidenceArtifactRef
    ) -> CalculationTableEvidence:
        return CalculationTableEvidence(
            calculation_id=result.result.calculation_table_id or f"calculate_{result.request_id}",
            table_id=result.object_id,
            source_table_ids=(result.dataset_id,),
            task_ids=result.task_ids,
            grain=result.partition_columns,
            input_columns=tuple(
                dict.fromkeys(
                    (
                        result.measure_column,
                        *result.partition_columns,
                        *((result.category_column,) if result.category_column is not None else ()),
                        *((result.time_column,) if result.time_column is not None else ()),
                    )
                )
            ),
            output_columns=result.result.value_paths,
            definition_ids=(result.method_id,),
            parameters={"decision": result.decision},
            row_ids=EvidenceBuilder._row_ids(result.result.values),
            content_hash=result.content_hash,
            complete=result.decision == "APPLICABLE",
            artifact=artifact,
        )

    @staticmethod
    def _quality_summary(bundle: DatasetBundle) -> EvidenceQualitySummary:
        failed = tuple(item for item in bundle.data_qa if not item.passed)
        blocked = tuple(item.message for item in failed if item.severity in {"ERROR", "FATAL"})
        material = tuple(
            dict.fromkeys(
                (
                    *(item.message for item in failed),
                    *bundle.warnings,
                    *(item.message for item in bundle.reconciliation if not item.passed),
                )
            )
        )
        status: Literal["VALID", "WARNING", "BLOCKED"] = (
            "BLOCKED" if blocked else "WARNING" if material else "VALID"
        )
        return EvidenceQualitySummary(
            status=status,
            material_warnings=material,
            blocked_reasons=blocked,
            completeness=tuple(
                f"{item.dataset_id}: {item.completeness.value}" for item in bundle.datasets
            ),
            reconciliation_summary=tuple(
                item.model_dump(mode="json") for item in bundle.reconciliation
            ),
            # Full DataQARecord objects remain in the owner-scoped AnswerSnapshot/debug
            # artifact and never enter the user Evidence Package.
            internal_qa_artifact=None,
        )

    @staticmethod
    def _metric_technical_payload(definition: MetricDefinition) -> dict[str, JsonValue]:
        return {
            "metric_id": definition.metric_id,
            "version": definition.version,
            "level": definition.level.value,
            "display_name": definition.display_name,
            "business_definition": definition.business_definition,
            "formula": EvidenceBuilder._metric_expression(definition),
            "numerator": (
                EvidenceBuilder._formula_expression(definition.numerator)
                if definition.numerator is not None
                else None
            ),
            "denominator": (
                EvidenceBuilder._formula_expression(definition.denominator)
                if definition.denominator is not None
                else None
            ),
            "source_field_ids": list(definition.source_field_ids),
            "value_dictionary_ids": list(definition.value_dictionary_ids),
            "dimensions": list(definition.dimensions),
            "aggregation_semantics": definition.aggregation_semantics.value,
            "unit": definition.unit,
            "precision": definition.precision,
            "null_policy": definition.null_policy,
            "pending_policy": definition.pending_policy,
            "unknown_policy": definition.unknown_policy,
            "minimum_denominator": definition.minimum_denominator,
            "time_semantics": (
                definition.time_semantics.model_dump(mode="json")
                if definition.time_semantics is not None
                else None
            ),
            "approximate": definition.approximate,
            "owner": definition.owner,
        }

    @classmethod
    def _metric_technical_definitions(
        cls, definitions: tuple[MetricDefinition, ...], used: set[str]
    ) -> tuple[TechnicalDefinitionEvidence, ...]:
        return tuple(
            TechnicalDefinitionEvidence(
                definition_id=item.versioned_id,
                definition_type="metric",
                version=item.version,
                display_name=item.display_name,
                purpose_or_business_definition=item.business_definition,
                technical_expression=cls._metric_expression(item),
                details=cls._metric_technical_payload(item),
            )
            for item in definitions
            if item.versioned_id in used
        )

    @staticmethod
    def _measure_technical_definitions(
        definitions: tuple[MeasureDefinition, ...], used: set[str]
    ) -> tuple[TechnicalDefinitionEvidence, ...]:
        return tuple(
            TechnicalDefinitionEvidence(
                definition_id=item.versioned_id,
                definition_type="measure",
                version=item.version,
                display_name=item.display_name,
                purpose_or_business_definition=item.business_definition,
                technical_expression=(
                    f"{item.default_aggregation.value}({item.source_field_id or 'documents'})"
                ),
                details={
                    "measure_id": item.measure_id,
                    "source_semantic_field_id": item.source_field_id,
                    "allowed_aggregations": [kind.value for kind in item.allowed_aggregations],
                    "aggregation_parameters": item.default_parameters.model_dump(mode="json"),
                    "unit": item.unit,
                    "source_grain": list(item.source_grain),
                    "population_scope": item.population_scope,
                    "aggregation_semantics": item.semantics.value,
                    "approximate": item.approximate,
                    "owner": item.owner,
                },
            )
            for item in definitions
            if item.versioned_id in used
        )

    @staticmethod
    def _method_technical_definitions(
        definitions: tuple[MethodDefinition, ...], used: set[str]
    ) -> tuple[TechnicalDefinitionEvidence, ...]:
        return tuple(
            TechnicalDefinitionEvidence(
                definition_id=item.method_id,
                definition_type="method",
                version=item.version,
                display_name=item.display_name,
                purpose_or_business_definition=item.purpose,
                technical_expression=item.technical_description,
                details={
                    "minimum_rows": item.minimum_rows,
                    "required_semantic_types": list(item.required_semantic_types),
                    "default_params": item.default_params,
                    "parameter_limits": item.parameter_limits,
                    "supported_partition_roles": list(item.supported_partition_roles),
                    "requires_category": item.requires_category,
                    "requires_time": item.requires_time,
                    "interpretation_limitations": list(item.interpretation_limitations),
                },
            )
            for item in definitions
            if item.method_id in used
        )

    @classmethod
    def _metric_expression(cls, definition: MetricDefinition) -> str:
        if definition.numerator is not None and definition.denominator is not None:
            return (
                f"({cls._formula_expression(definition.numerator)}) / "
                f"({cls._formula_expression(definition.denominator)})"
            )
        assert definition.formula is not None
        return cls._formula_expression(definition.formula)

    @classmethod
    def _formula_expression(cls, node: FormulaNode) -> str:
        if node.operator == "constant":
            return str(node.value)
        if node.operator == "column":
            return str(node.column)
        if node.operator == "filtered_count":
            return f"filtered_count({','.join(node.status_groups)})"
        expressions = tuple(cls._formula_expression(item) for item in node.operands)
        symbols = {"add": "+", "subtract": "-", "multiply": "*", "divide": "/"}
        if node.operator in symbols:
            return f" {symbols[node.operator]} ".join(expressions)
        return f"sum({', '.join(expressions)})"

    @classmethod
    def _leaf_bucket_count(cls, value: JsonValue) -> int:
        if isinstance(value, dict):
            buckets = value.get("buckets")
            if isinstance(buckets, list):
                total = sum(cls._leaf_bucket_count(item) for item in buckets)
                return total or len(buckets)
            if isinstance(buckets, dict):
                total = sum(cls._leaf_bucket_count(item) for item in buckets.values())
                return total or len(buckets)
            nested = sum(cls._leaf_bucket_count(item) for item in value.values())
            return nested
        if isinstance(value, list):
            return sum(cls._leaf_bucket_count(item) for item in value)
        return 0

    @staticmethod
    def _aggregation_kinds(value: Mapping[str, Any]) -> list[str]:
        allowed = {
            "terms",
            "composite",
            "date_histogram",
            "value_count",
            "cardinality",
            "sum",
            "avg",
            "min",
            "max",
            "stats",
            "extended_stats",
            "percentiles",
        }
        found: set[str] = set()

        def visit(item: Any) -> None:
            if isinstance(item, dict):
                found.update(set(item).intersection(allowed))
                for child in item.values():
                    visit(child)
            elif isinstance(item, list):
                for child in item:
                    visit(child)

        visit(value)
        return sorted(found)

    @classmethod
    def _row_ids(cls, value: JsonValue) -> tuple[str, ...]:
        if isinstance(value, dict):
            direct = tuple(
                str(child)
                for key, child in value.items()
                if (key == "row_id" or key.endswith("_row_id")) and isinstance(child, str)
            )
            nested = tuple(row_id for child in value.values() for row_id in cls._row_ids(child))
            return tuple(dict.fromkeys((*direct, *nested)))
        if isinstance(value, list):
            return tuple(dict.fromkeys(row_id for child in value for row_id in cls._row_ids(child)))
        return ()

    @staticmethod
    def _claim_reference_payload(
        reference: EvidenceRef,
        artifacts_by_table_id: Mapping[str, EvidenceArtifactRef],
    ) -> dict[str, JsonValue]:
        payload = reference.model_dump(mode="json")
        if reference.table_id is not None:
            artifact = artifacts_by_table_id.get(reference.table_id)
            if artifact is not None:
                payload["artifact_id"] = artifact.artifact_id
                payload["artifact_hash"] = artifact.content_hash
        return payload


class EvidenceAccessPolicy:
    def allow_advanced(self, identity: IdentityContext) -> bool:
        return bool({"analyst", "tester", "developer"}.intersection(identity.roles))

    def allow_debug(self, identity: IdentityContext) -> bool:
        return "developer" in identity.roles

    def allow_csv(self, identity: IdentityContext, dataset: TabularDataset) -> bool:
        classifications = {item.security_classification for item in dataset.columns}
        if "restricted" in classifications:
            return "developer" in identity.roles
        if "confidential" in classifications:
            return bool({"analyst", "tester", "developer"}.intersection(identity.roles))
        return True


class EvidenceExporter:
    def dataset_csv(self, dataset: TabularDataset) -> str:
        output = io.StringIO(newline="")
        columns = [item.name for item in dataset.columns]
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["row_id", *columns])
        for row in dataset.rows:
            writer.writerow(
                [row.row_id, *(self._csv_value(row.values.get(column)) for column in columns)]
            )
        return output.getvalue()

    @staticmethod
    def _csv_value(value: object) -> str | int | float | bool:
        if value is None:
            return ""
        text: str | int | float | bool
        if isinstance(value, dict | list):
            text = canonical_json(value)
        elif isinstance(value, str | int | float | bool):
            text = value
        else:
            text = str(value)
        if isinstance(text, str) and text.startswith(("=", "+", "-", "@")):
            return f"'{text}"
        return text
