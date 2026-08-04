"""Resolve structured claim selectors to unique dataset rows and evidence refs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from app.contracts.common import Provenance, StrictModel, semantic_hash
from app.contracts.dataset import DatasetBundle, DatasetColumn, DatasetRow, TabularDataset
from app.contracts.insight import ClaimDraft, ClaimSpec, EvidenceRef
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
    ) -> GroundingResult:
        claims: list[ClaimSpec] = []
        failures: list[GroundingFailure] = []
        datasets = {item.dataset_id: item for item in bundle.datasets}
        blocked_datasets = {
            item.dataset_id
            for item in bundle.data_qa
            if item.dataset_id is not None
            and item.severity in {"ERROR", "FATAL"}
            and not item.passed
        }
        for index, draft in enumerate(drafts):
            try:
                claims.append(self._ground_one(draft, datasets, blocked_datasets))
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
        blocked_datasets: set[str],
    ) -> ClaimSpec:
        if self.CAUSAL_TERMS.search(draft.template):
            raise ValueError("causal language is not supported by descriptive evidence")
        formatted: dict[str, str] = {}
        evidence: list[EvidenceRef] = []
        for binding in draft.bindings:
            dataset = datasets.get(binding.dataset_id)
            if dataset is None:
                raise ValueError(f"dataset does not exist: {binding.dataset_id}")
            if dataset.dataset_id in blocked_datasets:
                raise ValueError(f"dataset is blocked by ERROR/FATAL QA: {dataset.dataset_id}")
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
