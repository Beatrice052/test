"""Policy-filtered lexical semantic retrieval over compiled package documents."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from app.contracts.common import Provenance, semantic_hash
from app.contracts.semantic import CandidateItem, SemanticCandidateSet
from app.semantic.fts_index import search_fts
from app.semantic.package import read_json

DEFAULT_LIMITS = {
    "dataset": 5,
    "metric": 10,
    "measure": 20,
    "field": 20,
    "entity": 10,
    "recipe": 10,
    "method": 10,
    "value": 20,
}
type CandidateType = Literal[
    "dataset", "metric", "measure", "field", "entity", "recipe", "method", "value"
]


class SemanticRetriever:
    def __init__(self, package_dir: Path) -> None:
        self.package_dir = package_dir
        self.index_path = package_dir / "retrieval.db"

    def retrieve(
        self,
        query: str,
        *,
        allowed_item_ids: set[str] | None = None,
        limits: dict[str, int] | None = None,
    ) -> SemanticCandidateSet:
        resolved_limits = {**DEFAULT_LIMITS, **(limits or {})}
        rows = search_fts(self.index_path, query, limit=sum(resolved_limits.values()) * 3)
        grouped: dict[str, list[CandidateItem]] = {key: [] for key in DEFAULT_LIMITS}
        query_lower = query.lower().strip()
        for document, rank in rows:
            item_id = str(document["item_id"])
            item_type = str(document["item_type"])
            if item_type not in grouped:
                continue
            if allowed_item_ids is not None and item_id not in allowed_item_ids:
                continue
            exact_values = {
                item_id.lower(),
                str(document.get("display_name", "")).lower(),
                *(str(alias).lower() for alias in document.get("aliases", ())),
            }
            exact_bonus = 100.0 if query_lower in exact_values else 0.0
            if exact_bonus == 0 and any(
                len(value) >= 2 and value in query_lower for value in exact_values
            ):
                exact_bonus = 80.0
            score = exact_bonus + max(0.0, 50.0 - abs(rank))
            candidate = CandidateItem(
                item_id=item_id,
                item_type=cast(CandidateType, item_type),
                display_name=str(document.get("display_name") or item_id),
                summary=str(document.get("description") or document.get("summary") or ""),
                score=score,
                capabilities=tuple(document.get("capabilities", ())),
                metadata={
                    key: value
                    for key, value in document.items()
                    if key
                    not in {
                        "item_id",
                        "item_type",
                        "display_name",
                        "description",
                        "capabilities",
                    }
                },
            )
            grouped[item_type].append(candidate)

        for item_type, candidates in grouped.items():
            candidates.sort(key=lambda item: (-item.score, item.item_id))
            del candidates[resolved_limits[item_type] :]

        if not grouped["dataset"]:
            self._add_dataset_fallbacks(
                grouped["dataset"],
                allowed_item_ids=allowed_item_ids,
                limit=resolved_limits["dataset"],
            )
        self._add_registry_fallbacks(
            grouped,
            allowed_item_ids=allowed_item_ids,
            limits=resolved_limits,
        )
        self._add_confirmed_field_fallbacks(
            grouped["field"],
            allowed_item_ids=allowed_item_ids,
            limit=resolved_limits["field"],
        )

        created_at = datetime.now(UTC)
        payload: dict[str, Any] = {
            "query": query,
            "ids": {
                item_type: [item.item_id for item in candidates]
                for item_type, candidates in grouped.items()
            },
        }
        content_hash = semantic_hash(payload)
        return SemanticCandidateSet(
            object_id=f"scs_{content_hash.removeprefix('sha256:')[:16]}",
            created_at=created_at,
            content_hash=content_hash,
            provenance=Provenance(producer="semantic.retriever"),
            query=query,
            dataset_candidates=tuple(grouped["dataset"]),
            metric_candidates=tuple(grouped["metric"]),
            measure_candidates=tuple(grouped["measure"]),
            field_candidates=tuple(grouped["field"]),
            entity_candidates=tuple(grouped["entity"]),
            recipe_candidates=tuple(grouped["recipe"]),
            method_candidates=tuple(grouped["method"]),
            value_candidates=tuple(grouped["value"]),
            retrieval_version="fts5-bm25.v1",
        )

    def _add_dataset_fallbacks(
        self,
        candidates: list[CandidateItem],
        *,
        allowed_item_ids: set[str] | None,
        limit: int,
    ) -> None:
        documents = read_json(self.package_dir / "datasets.json")
        if not isinstance(documents, list):
            return
        for document in documents:
            if not isinstance(document, dict):
                continue
            item_id = str(document.get("dataset_id", ""))
            if not item_id or (allowed_item_ids is not None and item_id not in allowed_item_ids):
                continue
            candidates.append(
                CandidateItem(
                    item_id=item_id,
                    item_type="dataset",
                    display_name=str(document.get("display_name") or item_id),
                    summary=str(document.get("description") or ""),
                    score=0.0,
                    capabilities=(),
                    metadata={},
                )
            )
            if len(candidates) >= limit:
                break

    def _add_registry_fallbacks(
        self,
        grouped: dict[str, list[CandidateItem]],
        *,
        allowed_item_ids: set[str] | None,
        limits: dict[str, int],
    ) -> None:
        """Keep the small governed registries visible as bounded low-score candidates."""

        supported = {"metric", "measure", "entity", "recipe", "method", "value"}
        path = self.package_dir / "retrieval_documents.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            document = json.loads(line)
            if not isinstance(document, dict):
                continue
            item_type = str(document.get("item_type", ""))
            item_id = str(document.get("item_id", ""))
            if item_type not in supported or not item_id:
                continue
            candidates = grouped[item_type]
            if len(candidates) >= limits[item_type] or any(
                item.item_id == item_id for item in candidates
            ):
                continue
            if allowed_item_ids is not None and item_id not in allowed_item_ids:
                continue
            candidates.append(
                CandidateItem(
                    item_id=item_id,
                    item_type=cast(CandidateType, item_type),
                    display_name=str(document.get("display_name") or item_id),
                    summary=str(document.get("description") or ""),
                    score=0.0,
                    capabilities=tuple(document.get("capabilities", ())),
                    metadata={
                        "fallback": True,
                        **{
                            key: value
                            for key, value in document.items()
                            if key
                            not in {
                                "item_id",
                                "item_type",
                                "display_name",
                                "description",
                                "aliases",
                                "capabilities",
                            }
                        },
                    },
                )
            )

    def _add_confirmed_field_fallbacks(
        self,
        candidates: list[CandidateItem],
        *,
        allowed_item_ids: set[str] | None,
        limit: int,
    ) -> None:
        documents = read_json(self.package_dir / "fields.json")
        if not isinstance(documents, list):
            return
        for document in documents:
            if not isinstance(document, dict) or document.get("maturity") != "BUSINESS_CONFIRMED":
                continue
            item_id = str(document.get("field_id", ""))
            if not item_id or any(item.item_id == item_id for item in candidates):
                continue
            if allowed_item_ids is not None and item_id not in allowed_item_ids:
                continue
            candidates.append(
                CandidateItem(
                    item_id=item_id,
                    item_type="field",
                    display_name=str(document.get("display_name") or item_id),
                    summary=str(document.get("description") or ""),
                    score=0.0,
                    capabilities=tuple(document.get("capabilities", ())),
                    metadata={
                        "fallback": True,
                        "maturity": "BUSINESS_CONFIRMED",
                        "semantic_type": document.get("semantic_type"),
                        "business_domain": document.get("business_domain"),
                        "aliases": document.get("aliases", []),
                    },
                )
            )
            if len(candidates) >= limit:
                break
