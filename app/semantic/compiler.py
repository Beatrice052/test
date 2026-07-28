from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.semantic.models import (
    CanonicalField,
    CompilationResult,
    CompiledSemanticModel,
    DatasetDefinition,
    FieldAccess,
    ImportReport,
    MetricDefinition,
    QueryPolicy,
    SemanticMaturity,
)


@dataclass(frozen=True)
class SemanticSourcePaths:
    catalog: Path
    mapping: Path
    metrics: Path
    value_dictionary: Path
    policy: Path

    @classmethod
    def from_project_root(cls, project_root: Path) -> SemanticSourcePaths:
        source_dir = project_root / "semantic_sources"
        return cls(
            catalog=source_dir / "field_catalog_enrich.csv",
            mapping=source_dir / "mock_mapping.json",
            metrics=source_dir / "metric_registry.yaml",
            value_dictionary=source_dir / "value_dictionary.yaml",
            policy=source_dir / "policy.yaml",
        )


class SemanticCompilationError(ValueError):
    pass


class SemanticCompiler:
    def __init__(
        self,
        paths: SemanticSourcePaths,
        *,
        business_timezone: str = "Asia/Hong_Kong",
        model_version: str = "mock-semantic.v1",
        synthetic_sources: bool = True,
    ) -> None:
        self.paths = paths
        self.business_timezone = business_timezone
        self.model_version = model_version
        self.synthetic_sources = synthetic_sources

    def compile(self) -> CompilationResult:
        catalog_rows, duplicates = self._load_catalog()
        mapping_payload = self._load_json(self.paths.mapping)
        mapping_fields = self._flatten_mapping(mapping_payload)
        metrics_payload = self._load_yaml(self.paths.metrics)
        dictionaries_payload = self._load_yaml(self.paths.value_dictionary)
        policy_payload = self._load_yaml(self.paths.policy)

        policy = self._build_policy(policy_payload)
        blocked = set(policy.blocked_fields)
        review_required = set(policy.review_required_fields)
        explicitly_allowed_mapping_only = set(
            policy_payload.get("field_rules", {}).get("explicitly_allowed_mapping_only", [])
        )

        fields: list[CanonicalField] = []
        type_conflicts: list[dict[str, str]] = []
        mapping_only: list[str] = []
        matched = 0

        catalog_by_path = {row["field_path"]: row for row in catalog_rows}
        for field_path in sorted(mapping_fields):
            mapping_info = mapping_fields[field_path]
            catalog = catalog_by_path.get(field_path)
            if catalog is None:
                mapping_only.append(field_path)
                access = (
                    FieldAccess.ALLOWED
                    if field_path in explicitly_allowed_mapping_only
                    else FieldAccess.REVIEW_REQUIRED
                )
                maturity = SemanticMaturity.MAPPING_ONLY
            else:
                matched += 1
                access = self._resolve_access(catalog, field_path, blocked, review_required)
                maturity = (
                    SemanticMaturity.BLOCKED
                    if access is FieldAccess.BLOCKED
                    else SemanticMaturity.DOCUMENTED
                )
                declared_type = (catalog.get("mapping_type") or "").strip()
                if declared_type and declared_type != mapping_info["type"]:
                    type_conflicts.append(
                        {
                            "field_path": field_path,
                            "catalog_type": declared_type,
                            "mapping_type": mapping_info["type"],
                        }
                    )

            allowed_operations = self._allowed_operations(mapping_info)
            if access is not FieldAccess.ALLOWED:
                allowed_operations = []

            fields.append(
                CanonicalField(
                    field_path=field_path,
                    physical_aggregation_path=mapping_info["aggregation_path"],
                    mapping_type=mapping_info["type"],
                    searchable=mapping_info["searchable"],
                    aggregatable=mapping_info["aggregatable"],
                    description=(catalog or {}).get("business_description_en", "").strip(),
                    remarks=self._split_text((catalog or {}).get("business_remark_en", "")),
                    aliases=self._split_aliases((catalog or {}).get("aliases", "")),
                    field_group_hint=(catalog or {}).get("field_group", "").strip() or None,
                    value_dictionary=self._dictionary_for_field(
                        catalog or {}, dictionaries_payload
                    ),
                    usage_guidance=self._split_text(
                        (catalog or {}).get("chatbi_usage_guidance", "")
                    ),
                    analysis_caveats=self._split_text(
                        (catalog or {}).get("data_quality_or_metric_caveat", "")
                    ),
                    semantic_maturity=maturity,
                    sensitivity=(catalog or {}).get("sensitivity", "INTERNAL").strip()
                    or "INTERNAL",
                    access=access,
                    allowed_operations=allowed_operations,
                    source_refs=[
                        self.paths.mapping.name,
                        *([self.paths.catalog.name] if catalog else []),
                    ],
                    synthetic=self.synthetic_sources,
                )
            )

        catalog_only = sorted(set(catalog_by_path) - set(mapping_fields))
        field_map = {field.field_path: field for field in fields}
        metrics, invalid_bindings = self._build_metrics(metrics_payload, field_map)
        if invalid_bindings:
            raise SemanticCompilationError(
                f"invalid metric bindings: {', '.join(invalid_bindings)}"
            )

        sanitized_catalog = [
            {key: value for key, value in row.items() if key != "candidate_role"}
            for row in catalog_rows
        ]
        model = CompiledSemanticModel(
            model_version=self.model_version,
            dataset=DatasetDefinition(
                dataset_id=metrics_payload["dataset_id"],
                index_pattern=policy.index_pattern,
                default_time_field=metrics_payload["field_bindings"]["event_time"],
                business_timezone=self.business_timezone,
            ),
            fields=fields,
            metrics=metrics,
            value_dictionaries={
                key: {str(k): str(v) for k, v in value.items()}
                for key, value in dictionaries_payload.items()
                if isinstance(value, dict)
            },
            policy=policy,
            mapping_hash=self._stable_hash(mapping_payload),
            catalog_hash=self._stable_hash(sanitized_catalog),
            metric_hash=self._stable_hash(metrics_payload),
            policy_hash=self._stable_hash(policy_payload),
        )
        report = ImportReport(
            mapping_field_count=len(mapping_fields),
            catalog_row_count=len(catalog_rows),
            matched_count=matched,
            mapping_only_fields=mapping_only,
            catalog_only_fields=catalog_only,
            type_conflicts=type_conflicts,
            duplicate_field_paths=duplicates,
            invalid_metric_bindings=invalid_bindings,
            blocked_fields=sorted(
                field.field_path for field in fields if field.access is FieldAccess.BLOCKED
            ),
            review_required_fields=sorted(
                field.field_path for field in fields if field.access is FieldAccess.REVIEW_REQUIRED
            ),
            status=(
                "FAILED"
                if duplicates or invalid_bindings
                else "PASSED_WITH_WARNINGS"
                if catalog_only or mapping_only or type_conflicts
                else "PASSED"
            ),
            source_summary={
                "catalog": self.paths.catalog.name,
                "mapping": self.paths.mapping.name,
                "metrics": self.paths.metrics.name,
                "policy": self.paths.policy.name,
                "synthetic": self.synthetic_sources,
            },
        )
        if duplicates:
            raise SemanticCompilationError(f"duplicate field_path values: {', '.join(duplicates)}")
        return CompilationResult(model=model, report=report)

    def compile_to_directory(self, output_dir: Path) -> CompilationResult:
        result = self.compile()
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "compiled_semantic_model.json").write_text(
            result.model.model_dump_json(indent=2), encoding="utf-8"
        )
        (output_dir / "semantic_import_report.json").write_text(
            result.report.model_dump_json(indent=2), encoding="utf-8"
        )
        return result

    def _load_catalog(self) -> tuple[list[dict[str, str]], list[str]]:
        rows: list[dict[str, str]] = []
        seen: set[str] = set()
        duplicates: set[str] = set()
        with self.paths.catalog.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or "field_path" not in reader.fieldnames:
                raise SemanticCompilationError("catalog must contain field_path")
            for raw_row in reader:
                row = {key: (value or "") for key, value in raw_row.items()}
                field_path = row["field_path"].strip()
                if not field_path:
                    raise SemanticCompilationError("field_path cannot be blank")
                if field_path in seen:
                    duplicates.add(field_path)
                seen.add(field_path)
                row["field_path"] = field_path
                row.pop("candidate_role", None)
                rows.append(row)
        return rows, sorted(duplicates)

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SemanticCompilationError(f"{path.name} must contain an object")
        return payload

    @classmethod
    def _flatten_mapping(cls, payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        properties = payload.get("mappings", {}).get("properties")
        if not isinstance(properties, dict):
            raise SemanticCompilationError("mapping must contain mappings.properties")
        flattened: dict[str, dict[str, Any]] = {}

        def visit(current: dict[str, Any], prefix: str = "") -> None:
            for name, definition in current.items():
                path = f"{prefix}.{name}" if prefix else name
                mapping_type = definition.get("type", "object")
                keyword_subfield = (
                    mapping_type == "text"
                    and isinstance(definition.get("fields"), dict)
                    and definition["fields"].get("keyword", {}).get("type") == "keyword"
                )
                flattened[path] = {
                    "type": mapping_type,
                    "searchable": mapping_type not in {"object", "nested"},
                    "aggregatable": mapping_type
                    in {"keyword", "boolean", "date", "integer", "long", "float", "double"}
                    or keyword_subfield,
                    "aggregation_path": (f"{path}.keyword" if keyword_subfield else path),
                }
                child_properties = definition.get("properties")
                if isinstance(child_properties, dict):
                    visit(child_properties, path)

        visit(properties)
        return flattened

    @staticmethod
    def _allowed_operations(mapping_info: dict[str, Any]) -> list[str]:
        mapping_type = mapping_info["type"]
        if mapping_type == "keyword":
            return ["term", "terms", "group_by", "top_n"]
        if mapping_type == "boolean":
            return ["term", "terms", "group_by"]
        if mapping_type == "date":
            return ["range", "date_histogram", "min", "max"]
        if mapping_type in {"integer", "long", "float", "double"}:
            return ["range", "sum", "avg", "min", "max"]
        if mapping_type == "text":
            operations = ["match"]
            if mapping_info["aggregatable"]:
                operations.extend(["terms", "group_by", "top_n"])
            return operations
        return []

    @staticmethod
    def _resolve_access(
        catalog: dict[str, str],
        field_path: str,
        blocked: set[str],
        review_required: set[str],
    ) -> FieldAccess:
        declared = catalog.get("access", "").strip().lower()
        if field_path in blocked or declared == FieldAccess.BLOCKED:
            return FieldAccess.BLOCKED
        if field_path in review_required or declared == FieldAccess.REVIEW_REQUIRED:
            return FieldAccess.REVIEW_REQUIRED
        return FieldAccess.ALLOWED

    @staticmethod
    def _dictionary_for_field(
        catalog: dict[str, str], dictionaries: dict[str, Any]
    ) -> dict[str, str]:
        dictionary_name = catalog.get("value_dictionary", "").strip()
        dictionary = dictionaries.get(dictionary_name, {}) if dictionary_name else {}
        if not isinstance(dictionary, dict):
            return {}
        return {str(key): str(value) for key, value in dictionary.items()}

    @staticmethod
    def _split_aliases(value: str) -> list[str]:
        return [item.strip() for item in value.split("|") if item.strip()]

    @staticmethod
    def _split_text(value: str) -> list[str]:
        normalized = value.strip()
        return [normalized] if normalized else []

    @staticmethod
    def _build_policy(payload: dict[str, Any]) -> QueryPolicy:
        limits = payload["query_limits"]
        field_rules = payload.get("field_rules", {})
        return QueryPolicy(
            policy_version=payload["policy_version"],
            dataset_id=payload["dataset_id"],
            index_pattern=payload["index_pattern"],
            read_only=payload["read_only"],
            max_time_range_days=limits["max_time_range_days"],
            max_month_partitions=limits["max_month_partitions"],
            max_top_n=limits["max_top_n"],
            max_buckets=limits["max_buckets"],
            max_detail_size=limits["max_detail_size"],
            timeout_seconds=limits["timeout_seconds"],
            allow_scripts=payload["allow_scripts"],
            allow_generic_api=payload["allow_generic_api"],
            allow_raw_details=payload["allow_raw_details"],
            blocked_fields=list(field_rules.get("blocked", [])),
            review_required_fields=list(field_rules.get("review_required", [])),
        )

    @staticmethod
    def _build_metrics(
        payload: dict[str, Any], field_map: dict[str, CanonicalField]
    ) -> tuple[list[MetricDefinition], list[str]]:
        bindings = payload.get("field_bindings", {})
        invalid = [
            f"{role}:{field}"
            for role, field in bindings.items()
            if field not in field_map or field_map[field].access is not FieldAccess.ALLOWED
        ]
        metrics: list[MetricDefinition] = []
        for raw_metric in payload.get("metrics", {}).values():
            lifecycle_ref = raw_metric.get("lifecycle_field_ref")
            metrics.append(
                MetricDefinition(
                    metric_id=raw_metric["metric_id"],
                    version=raw_metric["version"],
                    status=payload["status"],
                    unit=raw_metric["unit"],
                    description=raw_metric.get("description", ""),
                    aggregation=raw_metric.get("aggregation"),
                    numerator_metric=raw_metric.get("numerator_metric"),
                    denominator_metric=raw_metric.get("denominator_metric"),
                    lifecycle_field=bindings.get(lifecycle_ref) if lifecycle_ref else None,
                    success_values=list(raw_metric.get("success_values", [])),
                    failed_values=list(raw_metric.get("failed_values", [])),
                    normalization=raw_metric.get("normalization"),
                    formula=raw_metric.get("formula"),
                    zero_denominator=raw_metric.get("zero_denominator"),
                    rounding_digits=raw_metric.get("rounding_digits", 2),
                    caveats=list(raw_metric.get("caveats", [])),
                )
            )
        return metrics, invalid

    @staticmethod
    def _stable_hash(payload: Any) -> str:
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"
