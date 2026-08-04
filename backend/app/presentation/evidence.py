"""Build immutable business/advanced evidence and safe tabular exports."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from app.contracts.analysis import AnalysisPlan
from app.contracts.common import Provenance, canonical_json, semantic_hash
from app.contracts.dataset import DatasetBundle, TabularDataset
from app.contracts.evidence import (
    AdvancedEvidence,
    BusinessEvidence,
    EvidencePackage,
    EvidenceRedaction,
)
from app.contracts.execution import ExecutionRecord
from app.contracts.insight import AnalyticsToolResult
from app.contracts.metric import MetricDefinition
from app.contracts.query import CompiledQuery, QueryPlan
from app.contracts.request import IdentityContext
from app.persistence.ids import new_id


class EvidenceBuilder:
    def build(
        self,
        *,
        analysis_plan: AnalysisPlan,
        query_plan: QueryPlan,
        compiled_queries: tuple[CompiledQuery, ...],
        executions: tuple[ExecutionRecord, ...],
        bundle: DatasetBundle,
        analytics_tool_results: tuple[AnalyticsToolResult, ...] = (),
        metric_definitions: tuple[MetricDefinition, ...],
        semantic_package_version: str,
    ) -> EvidencePackage:
        used_metrics = {
            metric_id for query in compiled_queries for metric_id in query.semantics.metric_ids
        }
        business = BusinessEvidence(
            scope={
                "analysis_plan_id": analysis_plan.object_id,
                "analysis_goal": analysis_plan.analysis_goal,
                "time_range": analysis_plan.scope.time_range.model_dump(mode="json"),
                "dataset_ids": list(analysis_plan.scope.dataset_ids),
                "semantic_package_version": semantic_package_version,
            },
            metric_definitions=tuple(
                {
                    "metric_id": item.metric_id,
                    "version": item.version,
                    "display_name": item.display_name,
                    "business_definition": item.business_definition,
                    "unit": item.unit,
                    "minimum_denominator": item.minimum_denominator,
                }
                for item in metric_definitions
                if item.versioned_id in used_metrics
            ),
            # Evidence links are immutable object references. Logical dataset names can be
            # reused by later questions and are retained in result_contracts for readers.
            data_tables=tuple(item.object_id for item in bundle.datasets),
            reconciliations=tuple(item.model_dump(mode="json") for item in bundle.reconciliation),
            quality=tuple(item.model_dump(mode="json") for item in bundle.data_qa),
            exploratory_analysis=tuple(
                {
                    "request_id": item.request_id,
                    "task_ids": list(item.task_ids),
                    "dataset_id": item.dataset_id,
                    "method_id": item.method_id,
                    "measure_column": item.measure_column,
                    "decision": item.decision,
                    "reason": item.reason,
                    "sample_size": item.result.sample_size,
                    "result": item.result.values,
                    "warnings": list(item.result.warnings),
                }
                for item in analytics_tool_results
            ),
            downloads=tuple(f"/api/v1/datasets/{item.object_id}/csv" for item in bundle.datasets),
        )
        advanced = AdvancedEvidence(
            query_plan=query_plan.model_dump(mode="json"),
            compiled_queries=tuple(item.model_dump(mode="json") for item in compiled_queries),
            execution_summaries=tuple(item.model_dump(mode="json") for item in executions),
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
        )
        redaction = EvidenceRedaction(
            removed_fields=(
                "credentials",
                "authorization_headers",
                "mcp_endpoint",
                "llm_prompt",
                "raw_documents",
            ),
            policy_id="evidence.v1",
        )
        payload = {
            "business": business.model_dump(mode="json"),
            "advanced": advanced.model_dump(mode="json"),
            "redaction": redaction.model_dump(mode="json"),
        }
        return EvidencePackage(
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
