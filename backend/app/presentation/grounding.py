"""Resolve structured claim selectors to unique dataset rows and evidence refs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from app.contracts.common import JsonValue, Provenance, StrictModel, semantic_hash
from app.contracts.dataset import DatasetBundle, DatasetColumn, DatasetRow, TabularDataset
from app.contracts.insight import (
    ClaimDraft,
    ClaimSpec,
    EvidenceRef,
    FeatureSummary,
    StatisticalResult,
)
from app.persistence.ids import new_id


class GroundingFailure(StrictModel):
    claim_index: int
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class GroundingResult:
    claims: tuple[ClaimSpec, ...]
    failures: tuple[GroundingFailure, ...]


class ClaimGrounder:
    CAUSAL_TERMS = re.compile(r"\b(caused?|because of|led to|resulted in)\b|导致|造成|引起", re.I)

    def ground(
        self,
        drafts: tuple[ClaimDraft, ...],
        bundle: DatasetBundle,
        *,
        feature_summaries: tuple[FeatureSummary, ...] = (),
    ) -> GroundingResult:
        claims: list[ClaimSpec] = []
        failures: list[GroundingFailure] = []
        datasets = {item.dataset_id: item for item in bundle.datasets}
        summaries = {item.dataset_id: item for item in feature_summaries}
        blocked_datasets = {
            item.dataset_id
            for item in bundle.data_qa
            if item.dataset_id is not None
            and item.severity in {"ERROR", "FATAL"}
            and not item.passed
        }
        for index, draft in enumerate(drafts):
            try:
                claims.append(self._ground_one(draft, datasets, summaries, blocked_datasets))
            except ValueError as error:
                failures.append(
                    GroundingFailure(
                        claim_index=index,
                        code="GROUNDING_REJECTED",
                        message=str(error),
                    )
                )
        return GroundingResult(tuple(claims), tuple(failures))

    def _ground_one(
        self,
        draft: ClaimDraft,
        datasets: dict[str, TabularDataset],
        summaries: dict[str, FeatureSummary],
        blocked_datasets: set[str],
    ) -> ClaimSpec:
        if self.CAUSAL_TERMS.search(draft.template):
            raise ValueError("causal language is not supported by descriptive evidence")
        if not draft.bindings:
            raise ValueError("claim requires at least one evidence binding")
        binding_names = tuple(item.name for item in draft.bindings)
        if len(set(binding_names)) != len(binding_names):
            raise ValueError("claim evidence binding names are not unique")
        formatted: dict[str, str] = {}
        evidence: list[EvidenceRef] = []
        for binding in draft.bindings:
            dataset = datasets.get(binding.dataset_id)
            if dataset is None:
                raise ValueError(f"dataset does not exist: {binding.dataset_id}")
            if dataset.dataset_id in blocked_datasets:
                raise ValueError(f"dataset is blocked by ERROR/FATAL QA: {dataset.dataset_id}")
            if binding.selector.startswith("statistic:"):
                result_selector = binding.selector.removeprefix("statistic:")
                result = self._statistical_result(
                    summaries.get(dataset.dataset_id), result_selector
                )
                value = self._statistical_value(result.values, binding.column)
                formatted[binding.name] = self._format_statistical_value(
                    value, result, dataset, binding.column
                )
                evidence.extend(self._statistical_evidence(dataset, result, binding.column))
                continue
            column = self._resolve_column(dataset, binding.column)
            row = self._select_row(dataset, binding.selector)
            value = row.values.get(column.name)
            if column.unit == "ratio":
                self._validate_ratio_evidence(row, column)
            formatted[binding.name] = self._format_value(value, column)
            evidence.append(
                EvidenceRef(
                    dataset_id=dataset.dataset_id,
                    row_id=row.row_id,
                    column=column.name,
                    table_id=dataset.object_id,
                    value_path=f"rows.{row.row_id}.{column.name}",
                    definition_ids=tuple(
                        item
                        for item in (
                            column.measure_id,
                            column.name if column.metric_id is not None else None,
                        )
                        if item is not None
                    ),
                    metric_id=column.metric_id,
                )
            )
        try:
            text = draft.template.format_map(formatted)
        except KeyError as error:
            raise ValueError(
                f"claim template has an unbound placeholder: {error.args[0]}"
            ) from error
        if "{" in text or "}" in text:
            raise ValueError("claim template has unresolved placeholders")
        payload = {
            "source_claim_id": draft.claim_id,
            "claim_type": draft.claim_type,
            "text": text,
            "importance": draft.importance,
            "task_ids": draft.task_ids,
            "evidence_refs": [item.model_dump(mode="json") for item in evidence],
        }
        return ClaimSpec(
            object_id=new_id("clm"),
            created_at=datetime.now(UTC),
            content_hash=semantic_hash(payload),
            provenance=Provenance(
                producer="presentation.claim_grounder",
                source_ids=tuple(dict.fromkeys(item.dataset_id for item in evidence)),
            ),
            source_claim_id=draft.claim_id,
            claim_type=draft.claim_type,
            text=text,
            importance=draft.importance,
            task_ids=draft.task_ids,
            evidence_refs=tuple(evidence),
        )

    @staticmethod
    def _statistical_result(summary: FeatureSummary | None, method_id: str) -> StatisticalResult:
        if summary is None:
            raise ValueError("statistical selector has no FeatureSummary")
        method_id, separator, source_column = method_id.partition("@")
        matches = [
            item
            for item in summary.statistical_results
            if item.method_id == method_id
            and item.applicability == "APPLICABLE"
            and (not separator or item.values.get("column") == source_column)
        ]
        if len(matches) != 1:
            raise ValueError(f"statistical selector is missing or ambiguous: {method_id}")
        return matches[0]

    @classmethod
    def _statistical_value(cls, values: dict[str, JsonValue], path: str) -> JsonValue:
        current: object = values
        for component in path.split("."):
            if isinstance(current, dict) and component in current:
                current = current[component]
                continue
            if isinstance(current, list) and component.isdigit():
                index = int(component)
                if 0 <= index < len(current):
                    current = current[index]
                    continue
            raise ValueError(f"statistical value path does not exist: {path}")
        if isinstance(current, dict | list):
            raise ValueError(f"statistical value path is not scalar: {path}")
        return cast(JsonValue, current)

    @classmethod
    def _format_statistical_value(
        cls,
        value: JsonValue,
        result: StatisticalResult,
        dataset: TabularDataset,
        path: str,
    ) -> str:
        if value is None:
            return "N/A"
        source_column_name = result.values.get("column")
        source_column = (
            cls._resolve_column(dataset, str(source_column_name))
            if isinstance(source_column_name, str)
            else None
        )
        ratio_paths = {
            "change_rate",
            "share",
            "cumulative_share",
            "coefficient_of_variation",
        }
        if isinstance(value, int | float) and not isinstance(value, bool):
            if path.rsplit(".", 1)[-1] in ratio_paths or (
                source_column is not None and source_column.unit == "ratio"
            ):
                return f"{float(value) * 100:.2f}%"
            return f"{float(value):.6g}"
        return str(value)

    @classmethod
    def _statistical_evidence(
        cls, dataset: TabularDataset, result: StatisticalResult, value_path: str
    ) -> tuple[EvidenceRef, ...]:
        referenced_row_ids = cls._row_ids(result.values)
        rows_by_id = {item.row_id: item for item in dataset.rows}
        selected_row_ids = [item for item in referenced_row_ids if item in rows_by_id]
        if not selected_row_ids:
            selected_row_ids = [item.row_id for item in dataset.rows[:100]]
        source_column = result.values.get("column")
        column = str(source_column) if isinstance(source_column, str) else "statistical_result"
        result_hash = semantic_hash(result)
        return tuple(
            EvidenceRef(
                dataset_id=dataset.dataset_id,
                row_id=row_id,
                column=column,
                table_id=result.calculation_table_id,
                value_path=f"result.values.{value_path}",
                definition_ids=(result.method_id,),
                statistical_method_id=result.method_id,
                statistical_result_hash=result_hash,
            )
            for row_id in dict.fromkeys(selected_row_ids)
        )

    @classmethod
    def _row_ids(cls, value: JsonValue) -> tuple[str, ...]:
        if isinstance(value, dict):
            direct = tuple(
                child
                for key, child in value.items()
                if (key == "row_id" or key.endswith("_row_id")) and isinstance(child, str)
            )
            nested = tuple(row_id for child in value.values() for row_id in cls._row_ids(child))
            combined = direct + nested
            return tuple(dict.fromkeys(combined))
        if isinstance(value, list):
            return tuple(dict.fromkeys(row_id for child in value for row_id in cls._row_ids(child)))
        return ()

    @staticmethod
    def _resolve_column(dataset: TabularDataset, requested: str) -> DatasetColumn:
        exact = [item for item in dataset.columns if item.name == requested]
        if len(exact) == 1:
            return exact[0]
        leaf = [item for item in dataset.columns if item.name.rsplit(".", 1)[-1] == requested]
        if len(leaf) == 1:
            return leaf[0]
        raise ValueError(f"column is missing or ambiguous: {requested}")

    def _select_row(self, dataset: TabularDataset, selector: str) -> DatasetRow:
        if selector == "first":
            if len(dataset.rows) != 1:
                raise ValueError("first selector requires exactly one row")
            return dataset.rows[0]
        if selector.startswith("argmax:") or selector.startswith("argmin:"):
            operation, requested = selector.split(":", 1)
            column = self._resolve_column(dataset, requested)
            candidates = [
                (row, value)
                for row in dataset.rows
                if isinstance((value := row.values.get(column.name)), int | float)
                and not isinstance(value, bool)
            ]
            if not candidates:
                raise ValueError(f"selector has no numeric rows: {selector}")
            target = (
                max(value for _, value in candidates)
                if operation == "argmax"
                else min(value for _, value in candidates)
            )
            matches = [row for row, value in candidates if value == target]
            if len(matches) != 1:
                raise ValueError(f"selector is not unique: {selector}")
            return matches[0]
        if selector.startswith("where:") and "=" in selector:
            expression = selector.removeprefix("where:")
            requested, expected = expression.split("=", 1)
            column = self._resolve_column(dataset, requested)
            matches = [row for row in dataset.rows if str(row.values.get(column.name)) == expected]
            if len(matches) != 1:
                raise ValueError(f"selector is not unique: {selector}")
            return matches[0]
        raise ValueError(f"selector is not allowed: {selector}")

    @staticmethod
    def _validate_ratio_evidence(row: DatasetRow, column: DatasetColumn) -> None:
        if column.metric_id is None:
            raise ValueError("ratio column lacks a governed metric ID")
        metadata = row.values.get("metric_metadata")
        item = metadata.get(column.metric_id) if isinstance(metadata, dict) else None
        denominator = item.get("denominator") if isinstance(item, dict) else None
        if (
            not isinstance(item, dict)
            or item.get("numerator") is None
            or denominator is None
            or denominator == 0
        ):
            raise ValueError("ratio claim lacks numerator/denominator evidence")

    @staticmethod
    def _format_value(value: object, column: DatasetColumn) -> str:
        if value is None:
            return "N/A"
        if (
            column.data_type == "datetime" or column.semantic_type == "time_dimension"
        ) and isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return value
            if parsed.day == 1 and parsed.hour == 0 and parsed.minute == 0:
                return f"{parsed.year}年{parsed.month:02d}月"
            return f"{parsed.year}年{parsed.month:02d}月{parsed.day:02d}日"
        if column.unit == "ratio" and isinstance(value, int | float):
            return f"{value * 100:.2f}%"
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)
