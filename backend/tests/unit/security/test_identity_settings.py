"""Identity mode is explicit for local profiles and safe for production."""

import pytest
from pydantic import ValidationError

from app.settings import AppSettings


def test_local_os_can_use_static_mock_identity_without_mock_gateway() -> None:
    settings = AppSettings(
        app_env="local-os",
        chatbi_identity_mode="mock",
        chatbi_llm_mode="rule_based",
        chatbi_gateway_mode="mcp",
    )

    assert settings.is_mock_profile is False
    assert settings.use_mock_identity is True


def test_production_rejects_mock_identity() -> None:
    with pytest.raises(ValidationError, match="production cannot use Mock identity"):
        AppSettings(
            app_env="production",
            chatbi_identity_mode="mock",
            chatbi_llm_mode="openai_compatible",
            chatbi_gateway_mode="mcp",
        )


@pytest.mark.parametrize("mode", ("fixture", "rule_based", "recorded"))
def test_production_rejects_non_live_llm_even_with_trusted_identity(mode: str) -> None:
    with pytest.raises(ValueError, match="non-live LLM"):
        AppSettings(
            app_env="production",
            chatbi_identity_mode="trusted_headers",
            chatbi_llm_mode=mode,  # type: ignore[arg-type]
            chatbi_gateway_mode="mcp",
        )


@pytest.mark.parametrize("mode", ("fixture", "rule_based", "recorded"))
def test_internal_mcp_profile_rejects_non_live_llm(mode: str) -> None:
    with pytest.raises(ValueError, match="non-live LLM"):
        AppSettings(
            app_env="mcp",
            chatbi_identity_mode="trusted_headers",
            chatbi_llm_mode=mode,  # type: ignore[arg-type]
            chatbi_gateway_mode="mcp",
        )


def test_internal_mcp_profile_rejects_mock_semantic_package() -> None:
    with pytest.raises(ValueError, match="Mock Semantic Package"):
        AppSettings(
            app_env="mcp",
            chatbi_identity_mode="trusted_headers",
            chatbi_llm_mode="openai_compatible",
            chatbi_llm_base_url="https://llm.internal/v1",
            chatbi_llm_model="approved-model",
            chatbi_gateway_mode="mcp",
            chatbi_semantic_package_dir="../compiled-semantic/mock",
            chatbi_semantic_input_dir="../semantic-input/internal",
        )


def test_internal_mcp_profile_rejects_mock_semantic_input() -> None:
    with pytest.raises(ValueError, match="Mock semantic input"):
        AppSettings(
            app_env="mcp",
            chatbi_identity_mode="trusted_headers",
            chatbi_llm_mode="openai_compatible",
            chatbi_llm_base_url="https://llm.internal/v1",
            chatbi_llm_model="approved-model",
            chatbi_gateway_mode="mcp",
            chatbi_semantic_package_dir="../compiled-semantic/internal",
            chatbi_semantic_input_dir="../semantic-input/mock",
        )


@pytest.mark.parametrize(
    ("package_dir", "input_dir"),
    (
        ("../compiled-semantic/internal", "../semantic-input/internal-template"),
        ("../compiled-semantic/internal-template", "../semantic-input/internal"),
    ),
)
def test_internal_mcp_profile_rejects_unreviewed_template_paths(
    package_dir: str, input_dir: str
) -> None:
    with pytest.raises(ValueError, match="cannot use internal-template directly"):
        AppSettings(
            app_env="mcp",
            chatbi_identity_mode="trusted_headers",
            chatbi_llm_mode="openai_compatible",
            chatbi_llm_base_url="https://llm.internal/v1",
            chatbi_llm_model="approved-model",
            chatbi_gateway_mode="mcp",
            chatbi_semantic_package_dir=package_dir,
            chatbi_semantic_input_dir=input_dir,
        )
