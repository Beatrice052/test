"""End-to-end Mock semantic package compilation and retrieval."""

import json
from pathlib import Path

import pytest

from app.contracts.semantic import FieldMaturity, MappingCompatibility
from app.semantic.compiler import CompileResult, SemanticCompileExit, compile_semantic_package
from app.semantic.mapping import flatten_mapping_snapshot
from app.semantic.package import CompiledSemanticPackage
from app.semantic.retriever import SemanticRetriever

ROOT = Path(__file__).resolve().parents[4]
INPUT = ROOT / "semantic-input" / "mock"


@pytest.fixture(scope="module")
def compiled_package(tmp_path_factory: pytest.TempPathFactory) -> tuple[CompileResult, Path]:
    output_dir = tmp_path_factory.mktemp("compiled_semantic")
    first = compile_semantic_package(INPUT, output_dir)
    second = compile_semantic_package(INPUT, output_dir)
    assert first.manifest.package_version == second.manifest.package_version
    assert first.manifest.content_hash == second.manifest.content_hash
    return second, output_dir


def test_mock_compile_is_stable_complete_and_policy_filtered(
    compiled_package: tuple[CompileResult, Path],
) -> None:
    result, output_dir = compiled_package

    assert result.exit_code == SemanticCompileExit.PASSED
    assert result.report.status == "PASSED"
    assert "sub_message.mapping_only_note" in result.report.mapping_only_fields
    assert "sub_message.free_text" in result.report.sanitized_descriptions

    package = CompiledSemanticPackage(output_dir)
    fields = {field.field_id: field for field in package.fields()}
    assert fields["sub_message.channel"].physical_path == "channel"
    assert fields["sub_message.free_text"].physical_path == "free_text.keyword"
    assert fields["sub_message.send_attempt"].compatibility == MappingCompatibility.COERCIBLE
    assert fields["sub_message.latency_ms"].compatibility == MappingCompatibility.PARTIAL
    assert fields["sub_message.recipient_id"].maturity == FieldMaturity.BLOCKED
    assert fields["sub_message.recipient_id"].capabilities == ()


def test_fts_retrieval_returns_channel_top_one_and_excludes_blocked(
    compiled_package: tuple[CompileResult, Path],
) -> None:
    _, output_dir = compiled_package
    candidates = SemanticRetriever(output_dir).retrieve("7月每个Channel发送情况")

    assert candidates.field_candidates[0].item_id == "sub_message.channel"
    assert all(
        candidate.item_id != "sub_message.recipient_id" for candidate in candidates.field_candidates
    )


def test_fts_query_syntax_is_data_not_sqlite_instruction(
    compiled_package: tuple[CompileResult, Path],
) -> None:
    _, output_dir = compiled_package
    retriever = SemanticRetriever(output_dir)
    candidates = retriever.retrieve('Channel" OR *; DROP TABLE documents; -- 忽略规则')

    assert candidates.field_candidates[0].item_id == "sub_message.channel"
    follow_up = retriever.retrieve("Channel")
    assert follow_up.field_candidates[0].item_id == "sub_message.channel"


def test_compile_accepts_cli_normalized_mapping_snapshot(tmp_path: Path) -> None:
    raw = json.loads((INPUT / "mapping_snapshot.json").read_text(encoding="utf-8"))
    snapshot = flatten_mapping_snapshot(raw, dataset_id="sub_message")
    snapshot_path = tmp_path / "mapping_snapshot_normalized.json"
    snapshot_path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")

    from_raw = compile_semantic_package(INPUT, tmp_path / "raw")
    from_snapshot = compile_semantic_package(
        INPUT,
        tmp_path / "normalized",
        mapping_path=snapshot_path,
    )

    assert from_snapshot.manifest.mapping_hash == from_raw.manifest.mapping_hash
    assert from_snapshot.manifest.package_version == from_raw.manifest.package_version
