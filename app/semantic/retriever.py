from __future__ import annotations

import re

from app.semantic.models import (
    CanonicalField,
    CompiledSemanticModel,
    FieldAccess,
    FieldCandidate,
)

TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]", re.IGNORECASE)


def _normalize(value: str) -> str:
    return " ".join(TOKEN_PATTERN.findall(value.casefold()))


def _tokens(value: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(value.casefold()))


class SemanticRetriever:
    def __init__(self, model: CompiledSemanticModel) -> None:
        self.model = model

    def retrieve(
        self,
        concept: str,
        *,
        required_operation: str | None = None,
        top_k: int = 5,
    ) -> list[FieldCandidate]:
        candidates: list[FieldCandidate] = []
        for field in self.model.fields:
            if field.access is not FieldAccess.ALLOWED:
                continue
            if required_operation and required_operation not in field.allowed_operations:
                continue
            score, matched_on = self._score(concept, field)
            if score <= 0:
                continue
            candidates.append(
                FieldCandidate(
                    concept=concept,
                    field_path=field.field_path,
                    score=round(score, 4),
                    matched_on=matched_on,
                    mapping_type=field.mapping_type,
                    allowed_operations=field.allowed_operations,
                    semantic_maturity=field.semantic_maturity,
                    caveats=field.analysis_caveats,
                )
            )
        candidates.sort(key=lambda item: (-item.score, item.field_path.casefold()))
        return candidates[:top_k]

    @staticmethod
    def _score(concept: str, field: CanonicalField) -> tuple[float, list[str]]:
        normalized_concept = _normalize(concept)
        concept_tokens = _tokens(concept)
        matched_on: list[str] = []
        score = 0.0

        if concept.strip() == field.field_path:
            score += 1.2
            matched_on.append("field_path_case_exact")
        elif normalized_concept == _normalize(field.field_path):
            score += 1.0
            matched_on.append("field_path_exact")
        elif normalized_concept and normalized_concept in _normalize(field.field_path):
            score += 0.55
            matched_on.append("field_path")

        normalized_aliases = [_normalize(alias) for alias in field.aliases]
        if normalized_concept in normalized_aliases:
            score += 0.9
            matched_on.append("alias_exact")
        elif any(
            normalized_concept and normalized_concept in alias for alias in normalized_aliases
        ):
            score += 0.45
            matched_on.append("alias")

        description_tokens = _tokens(
            " ".join(
                [
                    field.description,
                    *field.remarks,
                    *field.usage_guidance,
                    field.field_group_hint or "",
                ]
            )
        )
        if concept_tokens and description_tokens:
            overlap = len(concept_tokens & description_tokens) / len(concept_tokens)
            if overlap:
                score += 0.35 * overlap
                matched_on.append("description")

        dictionary_tokens = _tokens(" ".join(field.value_dictionary))
        if concept_tokens & dictionary_tokens:
            score += 0.3
            matched_on.append("value_dictionary")

        return score, matched_on
