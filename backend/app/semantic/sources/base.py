"""Knowledge source protocol and shared row normalization."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from app.contracts.semantic import FieldDescriptionRow
from app.semantic.sanitizer import DescriptionSanitizer

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "field_path": (
        "field_path",
        "field",
        "field_name",
        "column",
        "column_name",
        "字段",
        "字段名",
        "字段路径",
    ),
    "description": (
        "description",
        "desc",
        "definition",
        "business_description",
        "字段说明",
        "字段描述",
        "业务定义",
    ),
    "aliases": ("aliases", "alias", "synonyms", "别名", "同义词"),
    "business_domain": ("business_domain", "domain", "业务域", "主题域"),
    "usage_guidance": ("usage_guidance", "usage", "使用说明", "分析用途"),
    "value_meaning": ("value_meaning", "values", "枚举说明", "值说明"),
    "metric_caveat": ("metric_caveat", "caveat", "指标限制", "口径限制"),
    "sensitivity": ("sensitivity", "classification", "敏感等级", "数据分类"),
    "owner": ("owner", "业务owner", "负责人"),
    "confirmed": ("confirmed", "is_confirmed", "已确认", "业务确认"),
}
ALIAS_SEPARATOR_PATTERN = re.compile(r"[,;\uFF0C\uFF1B|\n]")


class KnowledgeSourceError(ValueError):
    """Invalid source shape that must be reported instead of guessed."""


class KnowledgeSourceAdapter(Protocol):
    """Extensible semantic knowledge source boundary."""

    source_path: Path

    def load_field_descriptions(self) -> list[FieldDescriptionRow]: ...


def normalize_header(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    return re.sub(r"\s+", "_", text)


def resolve_columns(headers: Sequence[object]) -> dict[str, int]:
    normalized = [normalize_header(header) for header in headers]
    resolved: dict[str, int] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        positions = [index for index, header in enumerate(normalized) if header in aliases]
        if len(positions) > 1:
            raise KnowledgeSourceError(f"duplicate columns for {canonical}: {positions}")
        if positions:
            resolved[canonical] = positions[0]
    missing = {"field_path", "description"} - resolved.keys()
    if missing:
        raise KnowledgeSourceError(f"missing required columns: {sorted(missing)}")
    return resolved


def parse_aliases(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    aliases = [item.strip() for item in ALIAS_SEPARATOR_PATTERN.split(str(value)) if item.strip()]
    return tuple(dict.fromkeys(aliases))


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "是", "已确认"}


def optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def build_description_row(
    values: Sequence[object],
    columns: Mapping[str, int],
    *,
    source_row: int,
    sanitizer: DescriptionSanitizer,
) -> FieldDescriptionRow | None:
    if not any(value not in {None, ""} for value in values):
        return None

    def cell(name: str) -> object:
        position = columns.get(name)
        return values[position] if position is not None and position < len(values) else None

    field_path = str(cell("field_path") or "").strip()
    description = str(cell("description") or "").strip()
    if not field_path or not description:
        raise KnowledgeSourceError(
            f"row {source_row} must contain non-empty field_path and description"
        )
    sanitized = sanitizer.sanitize(description)
    return FieldDescriptionRow(
        field_path=field_path,
        description=sanitized.text,
        aliases=parse_aliases(cell("aliases")),
        business_domain=optional_text(cell("business_domain")),
        usage_guidance=optional_text(cell("usage_guidance")),
        value_meaning=optional_text(cell("value_meaning")),
        metric_caveat=optional_text(cell("metric_caveat")),
        sensitivity=optional_text(cell("sensitivity")),
        owner=optional_text(cell("owner")),
        confirmed=parse_bool(cell("confirmed")),
        source_row=source_row,
        original_description_hash=sanitized.original_hash,
        sanitizer_events=sanitized.events,
    )
