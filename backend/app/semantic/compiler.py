"""Compile untrusted field metadata, Mapping, registries, and policy into one package."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import ValidationError

from app.contracts.common import Provenance, safe_identifier, semantic_hash
from app.contracts.metric import AggregationKind, FormulaNode
from app.contracts.semantic import (
    CanonicalField,
    CardinalityProfile,
    FieldDescriptionRow,
    FieldMaturity,
    FieldProfileSnapshot,
    FieldProvenance,
    FieldSecurity,
    ImportIssue,
    ImportReport,
    MappingCompatibility,
    MappingField,
    MappingSnapshot,
    SemanticManifest,
)
from app.registries import (
    DatasetRegistry,
    EntityRegistry,
    MeasureRegistry,
    MethodRegistry,
    MetricRegistry,
    PolicyRegistry,
    RecipeRegistry,
    ValueRegistry,
    VisualizationRegistry,
)
from app.registries.base import RegistryLoadError
from app.semantic.capability import (
    choose_mapping_variant,
    infer_capabilities,
    infer_compatibility,
    infer_semantic_type,
)
from app.semantic.fts_index import build_fts_index
from app.semantic.mapping import MappingFormatError, flatten_mapping_snapshot
from app.semantic.package import write_json
from app.semantic.sources import CsvFieldDescriptionAdapter, ExcelFieldDescriptionAdapter
from app.semantic.sources.base import KnowledgeSourceError


class SemanticCompileExit:
    PASSED = 0
    PASSED_WITH_WARNINGS = 2
    INVALID_INPUT = 10
    AMBIGUOUS_FIELD = 11
    MAPPING_CONFLICT = 12
    INVALID_METRIC = 13
    POLICY_VIOLATION = 14
    INTERNAL_ERROR = 20


class SemanticCompileError(RuntimeError):
    def __init__(self, message: str, *, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True, slots=True)
class CompileResult:
    manifest: SemanticManifest
    report: ImportReport
    fields: tuple[CanonicalField, ...]
    output_dir: Path
    exit_code: int


def _load_catalog(
    input_dir: Path, field_catalog_path: Path | None = None
) -> list[FieldDescriptionRow]:
    if field_catalog_path is not None:
        if field_catalog_path.suffix.lower() == ".xlsx":
            return ExcelFieldDescriptionAdapter(field_catalog_path).load_field_descriptions()
        if field_catalog_path.suffix.lower() == ".csv":
            return CsvFieldDescriptionAdapter(field_catalog_path).load_field_descriptions()
        raise SemanticCompileError(
            "field catalog must be .xlsx or .csv", exit_code=SemanticCompileExit.INVALID_INPUT
        )
    xlsx = input_dir / "field_descriptions.xlsx"
    csv_path = input_dir / "field_descriptions.csv"
    if xlsx.exists():
        return ExcelFieldDescriptionAdapter(xlsx).load_field_descriptions()
    if csv_path.exists():
        return CsvFieldDescriptionAdapter(csv_path).load_field_descriptions()
    raise SemanticCompileError(
        "field_descriptions.xlsx or field_descriptions.csv is required",
        exit_code=SemanticCompileExit.INVALID_INPUT,
    )


def _field_groups(fields: Sequence[MappingField]) -> dict[str, list[MappingField]]:
    groups: dict[str, list[MappingField]] = defaultdict(list)
    for field in fields:
        if field.mapping_type not in {"object", "nested"}:
            groups[field.source_path].append(field)
    return dict(groups)


def _resolve_catalog_path(
    field_path: str,
    groups: Mapping[str, Sequence[MappingField]],
) -> tuple[str | None, bool]:
    if field_path in groups:
        return field_path, False
    physical_matches = {
        source_path
        for source_path, variants in groups.items()
        if any(field.physical_path == field_path for field in variants)
    }
    if len(physical_matches) == 1:
        return next(iter(physical_matches)), False
    leaf_matches = {
        source_path for source_path in groups if source_path.rsplit(".", 1)[-1] == field_path
    }
    if len(leaf_matches) == 1:
        return next(iter(leaf_matches)), False
    return None, len(physical_matches | leaf_matches) > 1


def _retrieval_documents(
    fields: Sequence[CanonicalField],
    datasets: DatasetRegistry,
    metrics: MetricRegistry,
    measures: MeasureRegistry,
    entities: EntityRegistry,
    recipes: RecipeRegistry,
    methods: MethodRegistry,
    values: ValueRegistry,
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for field in fields:
        if field.maturity == FieldMaturity.BLOCKED or not field.security.model_visible:
            continue
        documents.append(
            {
                "item_id": field.field_id,
                "item_type": "field",
                "display_name": field.display_name,
                "aliases": field.aliases,
                "description": field.description or "",
                "business_domain": field.business_domain or "",
                "usage_guidance": " ".join(field.capabilities),
                "capabilities": field.capabilities,
                "maturity": field.maturity,
                "dataset_id": field.dataset_id,
                "mapping_type": field.mapping_type,
                "semantic_type": field.semantic_type,
                "compatibility": field.compatibility,
                "cardinality_estimate": field.cardinality.estimate,
                "cardinality_approximate": field.cardinality.approximate,
            }
        )
    for dataset in datasets.definitions:
        documents.append(
            {
                "item_id": dataset.dataset_id,
                "item_type": "dataset",
                "display_name": dataset.display_name,
                "description": dataset.description or "",
                "primary_time_field_id": dataset.primary_time_field_id,
                "default_timezone": dataset.default_timezone,
                "missing_index_policy": dataset.missing_index_policy,
            }
        )
    for metric in metrics.definitions:
        if metric.enabled:
            documents.append(
                {
                    "item_id": metric.versioned_id,
                    "item_type": "metric",
                    "display_name": metric.display_name,
                    "description": metric.business_definition,
                    "capabilities": metric.dimensions,
                    "level": metric.level,
                    "unit": metric.unit,
                    "minimum_denominator": metric.minimum_denominator,
                    "time_semantics": (
                        None
                        if metric.time_semantics is None
                        else metric.time_semantics.model_dump(mode="json")
                    ),
                }
            )
    model_visible_field_ids = {item.field_id for item in fields if item.security.model_visible}
    for measure in measures.definitions:
        if measure.enabled and (
            measure.source_field_id is None or measure.source_field_id in model_visible_field_ids
        ):
            documents.append(
                {
                    "item_id": measure.versioned_id,
                    "item_type": "measure",
                    "display_name": measure.display_name,
                    "description": measure.business_definition,
                    "capabilities": tuple(kind.value for kind in measure.allowed_aggregations),
                    "source_field_id": measure.source_field_id,
                    "default_aggregation": measure.default_aggregation,
                    "unit": measure.unit,
                    "semantics": measure.semantics,
                    "approximate": measure.approximate,
                }
            )
    for entity in entities.definitions:
        if entity.enabled:
            documents.append(
                {
                    "item_id": entity.versioned_id,
                    "item_type": "entity",
                    "display_name": entity.display_name,
                    "aliases": entity.aliases,
                    "description": entity.description,
                    "dataset_id": entity.dataset_id,
                    "identifier_field_id": entity.identifier_field_id,
                    "label_field_id": entity.label_field_id,
                    "member_resolution": entity.member_resolution,
                }
            )
    for recipe in recipes.definitions:
        documents.append(
            {
                "item_id": recipe.recipe_id,
                "item_type": "recipe",
                "display_name": recipe.question_archetype,
                "description": " ".join(recipe.minimum_capabilities),
                "capabilities": recipe.minimum_capabilities,
                "metric_ids": recipe.metric_ids,
                "method_ids": recipe.method_ids,
                "dimension_roles": recipe.dimension_roles,
                "visualization_intents": recipe.visualization_intents,
            }
        )
    for method in methods.definitions:
        documents.append(
            {
                "item_id": method.method_id,
                "item_type": "method",
                "display_name": method.display_name,
                "description": "exploratory statistical method",
                "capabilities": method.required_semantic_types,
                "minimum_rows": method.minimum_rows,
                "exploratory_label_required": method.exploratory_label_required,
                "default_params": method.default_params,
            }
        )
    for dictionary in values.definitions:
        for source_value, group in sorted(dictionary.values.items()):
            documents.append(
                {
                    "item_id": safe_identifier(
                        f"{dictionary.dictionary_id}.{dictionary.version}.{source_value}"
                    ),
                    "item_type": "value",
                    "display_name": source_value,
                    "description": group,
                    "dictionary_id": dictionary.dictionary_id,
                    "source_field_id": dictionary.source_field_id,
                }
            )
    return documents


def _formula_status_groups(node: FormulaNode | None) -> set[str]:
    if node is None:
        return set()
    return set(node.status_groups) | {
        group for operand in node.operands for group in _formula_status_groups(operand)
    }


def compile_semantic_package(
    input_dir: Path,
    output_dir: Path,
    *,
    field_catalog_path: Path | None = None,
    mapping_path: Path | None = None,
    profile_path: Path | None = None,
    metric_registry_path: Path | None = None,
) -> CompileResult:
    try:
        catalog_rows = _load_catalog(input_dir, field_catalog_path)
        raw_mapping = json.loads(
            (mapping_path or input_dir / "mapping_snapshot.json").read_text(encoding="utf-8")
        )
        resolved_profile_path = profile_path or input_dir / "field_profile_snapshot.json"
        raw_profile = (
            json.loads(resolved_profile_path.read_text(encoding="utf-8"))
            if resolved_profile_path.exists()
            else None
        )
        datasets = DatasetRegistry.load(input_dir / "dataset_registry.yaml")
        metrics = MetricRegistry.load(metric_registry_path or input_dir / "metric_registry")
        measures = MeasureRegistry.load(input_dir / "measures")
        entities = EntityRegistry.load(input_dir / "entities")
        values = ValueRegistry.load(input_dir / "values")
        recipes = RecipeRegistry.load(input_dir / "recipes")
        methods = MethodRegistry.load(input_dir / "methods")
        visualizations = VisualizationRegistry.load(input_dir / "visualizations")
        policies = PolicyRegistry.load(input_dir / "policy.yaml")
    except (
        OSError,
        json.JSONDecodeError,
        KnowledgeSourceError,
        RegistryLoadError,
        ValidationError,
    ) as error:
        raise SemanticCompileError(
            f"invalid semantic input: {error}", exit_code=SemanticCompileExit.INVALID_INPUT
        ) from error

    if len(datasets.definitions) != 1:
        raise SemanticCompileError(
            "POC compile requires exactly one dataset definition",
            exit_code=SemanticCompileExit.INVALID_INPUT,
        )
    dataset = datasets.definitions[0]
    try:
        if isinstance(raw_mapping, dict) and {"object_id", "fields", "raw_mapping_hash"}.issubset(
            raw_mapping
        ):
            mapping = MappingSnapshot.model_validate(raw_mapping, strict=False)
            if mapping.dataset_id != dataset.dataset_id:
                raise MappingFormatError("mapping snapshot dataset_id does not match registry")
        else:
            mapping = flatten_mapping_snapshot(raw_mapping, dataset_id=dataset.dataset_id)
    except (MappingFormatError, ValidationError) as error:
        raise SemanticCompileError(
            str(error), exit_code=SemanticCompileExit.MAPPING_CONFLICT
        ) from error

    profile: FieldProfileSnapshot | None = None
    if raw_profile is not None:
        try:
            profile = FieldProfileSnapshot.model_validate(raw_profile, strict=False)
            if profile.dataset_id != dataset.dataset_id:
                raise ValueError("field profile dataset_id does not match registry")
            if profile.mapping_content_hash != mapping.content_hash:
                raise ValueError("field profile was captured from a different Mapping snapshot")
            if profile.indices != mapping.indices:
                raise ValueError("field profile indices do not match Mapping snapshot indices")
        except (ValidationError, ValueError) as error:
            raise SemanticCompileError(
                f"invalid field profile snapshot: {error}",
                exit_code=SemanticCompileExit.INVALID_INPUT,
            ) from error
    profiles_by_source = {item.source_path: item for item in profile.fields} if profile else {}

    groups = _field_groups(mapping.fields)
    issues: list[ImportIssue] = []
    catalog_by_source: dict[str, Any] = {}
    catalog_only: list[str] = []
    duplicate_paths: list[str] = []
    ambiguous_rows: list[int] = []
    sanitized_paths: list[str] = []
    for row in catalog_rows:
        resolved, ambiguous = _resolve_catalog_path(row.field_path, groups)
        if ambiguous:
            ambiguous_rows.append(row.source_row)
            issues.append(
                ImportIssue(
                    code="AMBIGUOUS_FIELD",
                    severity="FATAL",
                    message="leaf field name maps to multiple Mapping paths",
                    field_path=row.field_path,
                    source_row=row.source_row,
                )
            )
            continue
        if resolved is None:
            catalog_only.append(row.field_path)
            issues.append(
                ImportIssue(
                    code="CATALOG_ONLY_FIELD",
                    severity="WARNING",
                    message="catalog field is absent from Mapping",
                    field_path=row.field_path,
                    source_row=row.source_row,
                )
            )
            continue
        existing = catalog_by_source.get(resolved)
        if existing is not None:
            duplicate_paths.append(resolved)
            severity: Literal["FATAL", "INFO"] = (
                "FATAL" if existing.description != row.description else "INFO"
            )
            issues.append(
                ImportIssue(
                    code="DUPLICATE_FIELD_PATH",
                    severity=severity,
                    message="duplicate catalog field path",
                    field_path=resolved,
                    source_row=row.source_row,
                )
            )
            continue
        catalog_by_source[resolved] = row
        if row.sanitizer_events:
            sanitized_paths.append(safe_identifier(f"{dataset.dataset_id}.{resolved}"))

    policy = policies.definitions[0]
    if dataset.dataset_id not in policy.allowed_dataset_ids:
        raise SemanticCompileError(
            f"dataset {dataset.dataset_id} is not allowed by policy",
            exit_code=SemanticCompileExit.POLICY_VIOLATION,
        )

    canonical_fields: list[CanonicalField] = []
    type_conflicts: list[str] = []
    mapping_only: list[str] = []
    blocked_fields: list[str] = []
    for source_path, variants in sorted(groups.items()):
        chosen = choose_mapping_variant(variants)
        field_id = safe_identifier(f"{dataset.dataset_id}.{source_path}")
        description = catalog_by_source.get(source_path)
        field_profile = profiles_by_source.get(source_path)
        compatibility = infer_compatibility(variants, all_indices=mapping.indices)
        if compatibility == MappingCompatibility.CONFLICT:
            type_conflicts.append(field_id)
        if description is None:
            mapping_only.append(field_id)
        blocked = field_id in policy.blocked_field_ids
        if blocked:
            blocked_fields.append(field_id)
        maturity = (
            FieldMaturity.BLOCKED
            if blocked
            else FieldMaturity.BUSINESS_CONFIRMED
            if description is not None and description.confirmed
            else FieldMaturity.DOCUMENTED
            if description is not None
            else FieldMaturity.PROFILED
            if field_profile is not None
            else FieldMaturity.MAPPING_ONLY
        )
        capabilities = () if blocked else infer_capabilities(variants)
        classification_value = (
            "restricted"
            if field_id in policy.sensitive_field_ids
            else (
                description.sensitivity if description and description.sensitivity else "internal"
            )
        )
        if classification_value not in {"public", "internal", "confidential", "restricted"}:
            classification_value = "internal"
        classification = cast(
            Literal["public", "internal", "confidential", "restricted"],
            classification_value,
        )
        field_payload = {
            "field_id": field_id,
            "physical_path": chosen.physical_path,
            "mapping_type": chosen.mapping_type,
            "compatibility": compatibility,
            "description": description.description if description else None,
            "capabilities": capabilities,
            "cardinality": (
                field_profile.cardinality_estimate if field_profile is not None else None
            ),
        }
        field_hash = semantic_hash(field_payload)
        canonical_fields.append(
            CanonicalField(
                object_id=f"fld_{field_hash.removeprefix('sha256:')[:16]}",
                created_at=mapping.captured_at,
                content_hash=field_hash,
                provenance=Provenance(
                    producer="semantic.compiler",
                    source_ids=(mapping.object_id,),
                    source_hashes={
                        "mapping": mapping.content_hash,
                        **(
                            {"profile": profile.content_hash}
                            if field_profile is not None and profile is not None
                            else {}
                        ),
                    },
                ),
                field_id=field_id,
                dataset_id=dataset.dataset_id,
                physical_path=chosen.physical_path,
                source_path=source_path,
                mapping_type=chosen.mapping_type,
                semantic_type=infer_semantic_type(chosen, description),
                display_name=(
                    description.aliases[0]
                    if description and description.aliases
                    else source_path.rsplit(".", 1)[-1]
                ),
                description=description.description if description else None,
                aliases=description.aliases if description else (),
                business_domain=description.business_domain if description else None,
                maturity=maturity,
                capabilities=capabilities,
                compatibility=compatibility,
                cardinality=CardinalityProfile(
                    estimate=(
                        field_profile.cardinality_estimate if field_profile is not None else None
                    ),
                    approximate=(
                        field_profile.cardinality_approximate
                        if field_profile is not None
                        else False
                    ),
                    profiled_at=profile.captured_at
                    if field_profile is not None and profile
                    else None,
                ),
                security=FieldSecurity(
                    classification=classification,
                    aggregatable=chosen.aggregatable and not blocked,
                    detail_visible=field_id in policy.detail_allowed_field_ids and not blocked,
                    model_visible=field_id not in policy.sensitive_field_ids and not blocked,
                ),
                field_provenance=FieldProvenance(
                    mapping_hash=mapping.content_hash,
                    catalog_row=description.source_row if description else None,
                    owner=description.owner if description else None,
                    sanitized=bool(description and description.sanitizer_events),
                ),
                observed_in_indices=tuple(
                    sorted({index for variant in variants for index in variant.observed_in_indices})
                ),
            )
        )

    canonical_field_ids = {field.field_id for field in canonical_fields}
    available_status_groups = {
        group for dictionary in values.definitions for group in dictionary.values.values()
    } | {dictionary.null_group for dictionary in values.definitions}
    missing_dictionary_fields = {
        dictionary.source_field_id
        for dictionary in values.definitions
        if dictionary.source_field_id not in canonical_field_ids
    }
    invalid_metric_bindings: list[str] = []
    for metric in metrics.definitions:
        required_groups = _formula_status_groups(metric.numerator) | _formula_status_groups(
            metric.denominator
        )
        if required_groups - available_status_groups or (
            required_groups and missing_dictionary_fields
        ):
            invalid_metric_bindings.append(metric.versioned_id)
            issues.append(
                ImportIssue(
                    code="INVALID_METRIC_BINDING",
                    severity="FATAL",
                    message="metric formula references unavailable status groups or source fields",
                    field_path=metric.versioned_id,
                    details={
                        "missing_status_groups": sorted(required_groups - available_status_groups),
                        "missing_dictionary_fields": sorted(missing_dictionary_fields),
                    },
                )
            )

    for measure in measures.definitions:
        if not measure.enabled or measure.source_field_id is None:
            continue
        field = next(
            (item for item in canonical_fields if item.field_id == measure.source_field_id), None
        )
        missing_capabilities = {
            f"aggregate_{kind.value}"
            for kind in measure.allowed_aggregations
            if kind != AggregationKind.DOCUMENT_COUNT
        } - (set(field.capabilities) if field is not None else set())
        if field is None or missing_capabilities:
            invalid_metric_bindings.append(measure.versioned_id)
            issues.append(
                ImportIssue(
                    code="INVALID_MEASURE_BINDING",
                    severity="FATAL",
                    message="measure source field is missing or lacks aggregation capability",
                    field_path=measure.versioned_id,
                    details={"missing_capabilities": sorted(missing_capabilities)},
                )
            )
    for entity in entities.definitions:
        if not entity.enabled:
            continue
        required = {entity.identifier_field_id} | (
            {entity.label_field_id} if entity.label_field_id is not None else set()
        )
        missing = required - canonical_field_ids
        if entity.dataset_id != dataset.dataset_id or missing:
            invalid_metric_bindings.append(entity.versioned_id)
            issues.append(
                ImportIssue(
                    code="INVALID_ENTITY_BINDING",
                    severity="FATAL",
                    message="entity references an unavailable dataset or field",
                    field_path=entity.versioned_id,
                    details={"missing_fields": sorted(missing)},
                )
            )

    fatal = any(issue.severity == "FATAL" for issue in issues)
    if type_conflicts:
        issues.extend(
            ImportIssue(
                code="MAPPING_TYPE_CONFLICT",
                severity="FATAL",
                message="field has incompatible types across indices",
                field_path=field_id,
            )
            for field_id in type_conflicts
        )
        fatal = True

    catalog_hash = semantic_hash([row.model_dump(mode="json") for row in catalog_rows])
    report_status: Literal["FAILED", "PASSED_WITH_WARNINGS", "PASSED"] = (
        "FAILED" if fatal else "PASSED_WITH_WARNINGS" if catalog_only else "PASSED"
    )
    report_payload = {
        "mapping_hash": mapping.content_hash,
        "catalog_hash": catalog_hash,
        "issues": [issue.model_dump(mode="json") for issue in issues],
    }
    report_hash = semantic_hash(report_payload)
    report = ImportReport(
        object_id=f"imr_{report_hash.removeprefix('sha256:')[:16]}",
        created_at=mapping.captured_at,
        content_hash=report_hash,
        provenance=Provenance(
            producer="semantic.compiler",
            source_ids=(mapping.object_id,),
            source_hashes={"mapping": mapping.content_hash, "catalog": catalog_hash},
        ),
        status=report_status,
        mapping_field_count=len(mapping.fields),
        catalog_row_count=len(catalog_rows),
        matched_count=len(catalog_by_source),
        mapping_only_fields=tuple(mapping_only),
        catalog_only_fields=tuple(sorted(catalog_only)),
        duplicate_field_paths=tuple(sorted(set(duplicate_paths))),
        ambiguous_rows=tuple(sorted(ambiguous_rows)),
        type_conflicts=tuple(type_conflicts),
        invalid_metric_bindings=tuple(invalid_metric_bindings),
        blocked_fields=tuple(blocked_fields),
        sanitized_descriptions=tuple(sorted(sanitized_paths)),
        mapping_hash=mapping.content_hash,
        catalog_hash=catalog_hash,
        issues=tuple(issues),
    )
    if fatal:
        output_dir.mkdir(parents=True, exist_ok=True)
        write_json(output_dir / "import_report.json", report)
        raise SemanticCompileError(
            "semantic compile contains blocking conflicts",
            exit_code=(
                SemanticCompileExit.AMBIGUOUS_FIELD
                if ambiguous_rows
                else SemanticCompileExit.MAPPING_CONFLICT
                if type_conflicts
                else SemanticCompileExit.INVALID_METRIC
                if invalid_metric_bindings
                else SemanticCompileExit.INVALID_INPUT
            ),
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    payloads: dict[str, Any] = {
        "datasets.json": datasets.definitions,
        "fields.json": canonical_fields,
        "metrics.json": metrics.definitions,
        "measures.json": measures.definitions,
        "entities.json": entities.definitions,
        "values.json": values.definitions,
        "recipes.json": recipes.definitions,
        "methods.json": methods.definitions,
        "visualizations.json": visualizations.definitions,
        "policies.json": policies.definitions,
        "import_report.json": report,
    }
    if profile is not None:
        payloads["field_profiles.json"] = profile.fields
    file_hashes: dict[str, str] = {}
    for name, payload in payloads.items():
        write_json(output_dir / name, payload)
        normalized = (
            [item.model_dump(mode="json") for item in payload]
            if isinstance(payload, (list, tuple))
            else payload.model_dump(mode="json")
        )
        file_hashes[name] = semantic_hash(normalized)

    documents = _retrieval_documents(
        canonical_fields, datasets, metrics, measures, entities, recipes, methods, values
    )
    retrieval_path = output_dir / "retrieval_documents.jsonl"
    retrieval_text = "".join(
        json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n" for document in documents
    )
    retrieval_path.write_text(retrieval_text, encoding="utf-8", newline="\n")
    file_hashes["retrieval_documents.jsonl"] = semantic_hash(documents)
    build_fts_index(output_dir / "retrieval.db", documents)

    registry_hash = semantic_hash(
        {
            name: file_hash
            for name, file_hash in file_hashes.items()
            if name not in {"fields.json", "field_profiles.json", "import_report.json"}
        }
    )
    package_hash = semantic_hash(
        {
            "mapping": mapping.content_hash,
            "catalog": catalog_hash,
            "registry": registry_hash,
            "fields": file_hashes["fields.json"],
            "profile": profile.content_hash if profile is not None else None,
            "retrieval": semantic_hash(documents),
        }
    )
    manifest = SemanticManifest(
        object_id=f"spm_{package_hash.removeprefix('sha256:')[:16]}",
        created_at=mapping.captured_at,
        content_hash=package_hash,
        provenance=Provenance(
            producer="semantic.compiler",
            source_ids=(mapping.object_id,),
            source_hashes={"mapping": mapping.content_hash, "catalog": catalog_hash},
        ),
        package_version=f"sp_{package_hash.removeprefix('sha256:')[:16]}",
        compiled_at=mapping.captured_at,
        dataset_ids=(dataset.dataset_id,),
        file_hashes=file_hashes,
        mapping_hash=mapping.content_hash,
        catalog_hash=catalog_hash,
        registry_hash=registry_hash,
    )
    write_json(output_dir / "manifest.json", manifest)
    exit_code = (
        SemanticCompileExit.PASSED_WITH_WARNINGS
        if report.status == "PASSED_WITH_WARNINGS"
        else SemanticCompileExit.PASSED
    )
    return CompileResult(
        manifest=manifest,
        report=report,
        fields=tuple(canonical_fields),
        output_dir=output_dir,
        exit_code=exit_code,
    )
