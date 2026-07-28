from __future__ import annotations

from pathlib import Path

from app.semantic.compiler import SemanticCompiler, SemanticSourcePaths
from app.semantic.retriever import SemanticRetriever

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _retriever() -> SemanticRetriever:
    result = SemanticCompiler(SemanticSourcePaths.from_project_root(PROJECT_ROOT)).compile()
    return SemanticRetriever(result.model)


def test_exact_field_name_has_priority_over_case_variant() -> None:
    candidates = _retriever().retrieve("status")

    assert candidates[0].field_path == "status"
    assert candidates[0].matched_on[0] == "field_path_case_exact"
    assert any(candidate.field_path == "Status" for candidate in candidates)


def test_chinese_alias_retrieves_channel() -> None:
    candidates = _retriever().retrieve("渠道", required_operation="group_by")

    assert candidates[0].field_path == "channel"


def test_blocked_fields_never_enter_candidates() -> None:
    candidates = _retriever().retrieve("消息正文")

    assert candidates == []


def test_operation_filter_removes_non_aggregatable_text() -> None:
    candidates = _retriever().retrieve("诊断", required_operation="group_by")

    assert all(candidate.field_path != "diagnosticText" for candidate in candidates)
