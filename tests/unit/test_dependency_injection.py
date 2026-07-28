from __future__ import annotations

from pathlib import Path

import pytest

from app.config.settings import Settings
from app.gateway.mock import MockOpenSearchGateway
from app.main import create_app
from app.semantic.compiler import SemanticCompiler, SemanticSourcePaths

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_mcp_mode_requires_injected_gateway() -> None:
    with pytest.raises(RuntimeError, match="MCPOpenSearchGateway"):
        create_app(Settings(data_source_mode="mcp"))


def test_structured_llm_mode_requires_injected_client() -> None:
    with pytest.raises(RuntimeError, match="injected LLMClient"):
        create_app(Settings(intent_backend="structured_llm"))


def test_connected_gateway_can_be_injected_without_rewriting_app() -> None:
    gateway = MockOpenSearchGateway(
        PROJECT_ROOT / "mock_data",
        PROJECT_ROOT / "semantic_sources" / "mock_mapping.json",
    )

    app = create_app(Settings(data_source_mode="mcp"), gateway=gateway)

    assert app.state.gateway is gateway
    assert app.state.connection_status == "connected"


def test_precompiled_semantic_model_is_shared_by_the_app() -> None:
    settings = Settings(semantic_model_version="internal-semantic.v1")
    compilation = SemanticCompiler(
        SemanticSourcePaths.from_project_root(PROJECT_ROOT),
        model_version=settings.semantic_model_version,
        synthetic_sources=False,
    ).compile()

    app = create_app(settings, semantic_compilation=compilation)

    assert app.state.semantic_compilation is compilation
    assert app.state.chatbi_agent.model is compilation.model
    assert all(not field.synthetic for field in compilation.model.fields)
    assert compilation.report.source_summary["synthetic"] is False


def test_injected_semantic_version_mismatch_fails_fast() -> None:
    compilation = SemanticCompiler(
        SemanticSourcePaths.from_project_root(PROJECT_ROOT),
        model_version="internal-semantic.v2",
    ).compile()

    with pytest.raises(RuntimeError, match="semantic model version"):
        create_app(
            Settings(semantic_model_version="internal-semantic.v1"),
            semantic_compilation=compilation,
        )
