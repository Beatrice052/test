"""Application settings with safe Mock-first defaults."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Runtime configuration. Secrets are read from environment only."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_log_level: str = "INFO"
    app_database_url: str = "sqlite:///./var/chatbi.db"
    app_artifact_dir: Path = Path("./var/artifacts")
    app_checkpoint_path: Path = Path("./var/checkpoints.db")

    chatbi_semantic_package_dir: Path = Path("../compiled-semantic/mock")
    chatbi_semantic_input_dir: Path = Path("../semantic-input/mock")
    chatbi_default_timezone: str = "Asia/Hong_Kong"
    chatbi_default_locale: str = "zh-CN"
    chatbi_debug_api_enabled: bool = False
    chatbi_identity_mode: Literal["mock", "trusted_headers"] | None = None

    chatbi_llm_mode: Literal["fixture", "rule_based", "openai_compatible", "recorded"] = "fixture"
    chatbi_llm_fixture_path: Path = Path("../fixtures/llm/analysis_plans.json")
    chatbi_llm_recording_path: Path = Path("../fixtures/llm/analysis_plans.json")
    chatbi_llm_base_url: str | None = None
    chatbi_llm_api_key: SecretStr | None = None
    chatbi_llm_model: str | None = None
    chatbi_llm_timeout_seconds: float = Field(default=30, gt=0, le=300)
    chatbi_gateway_mode: Literal["mock", "mcp", "direct"] = "mock"
    chatbi_gateway_config_path: Path = Path("../config/gateway.mcp.yaml")
    chatbi_gateway_fixture_path: Path = Path("../fixtures/gateway/sub_message_rows.json")

    opensearch_mcp_transport: Literal["stdio", "streamable_http", "sse_legacy"] = "streamable_http"
    opensearch_mcp_endpoint: str | None = None
    opensearch_mcp_command: str | None = None
    opensearch_mcp_args_json: tuple[str, ...] = ()
    opensearch_mcp_call_timeout_seconds: float = Field(default=35, gt=0, le=300)

    chatbi_max_queries_per_turn: int = Field(default=3, ge=1, le=10)
    chatbi_max_total_buckets: int = Field(default=5000, ge=1)
    chatbi_max_composite_pages: int = Field(default=20, ge=1, le=100)
    chatbi_max_raw_response_bytes: int = Field(default=10_000_000, ge=1024)
    chatbi_max_detail_hits: int = Field(default=100, ge=0, le=1000)
    chatbi_turn_timeout_seconds: int = Field(default=90, ge=1, le=600)

    @property
    def is_mock_profile(self) -> bool:
        """Return whether all external dependencies are deterministic local adapters."""

        return self.chatbi_llm_mode in {"fixture", "rule_based", "recorded"} and (
            self.chatbi_gateway_mode == "mock"
        )

    @property
    def use_mock_identity(self) -> bool:
        """Use a fixed local identity only when the profile explicitly allows it."""

        if self.chatbi_identity_mode is not None:
            return self.chatbi_identity_mode == "mock"
        return self.is_mock_profile

    @model_validator(mode="after")
    def forbid_mock_identity_in_production(self) -> Self:
        environment = self.app_env.lower()
        formal_environments = {"prod", "production", "mcp"}
        if environment in formal_environments and self.use_mock_identity:
            label = "production" if environment in {"prod", "production"} else "mcp"
            raise ValueError(f"{label} cannot use Mock identity")
        if environment in formal_environments and self.chatbi_llm_mode in {
            "fixture",
            "rule_based",
            "recorded",
        }:
            raise ValueError("mcp/production cannot use a Mock/non-live LLM adapter")
        if environment in formal_environments and self.chatbi_gateway_mode != "mcp":
            raise ValueError("mcp/production requires the approved MCP Gateway")
        semantic_parts = {part.casefold() for part in self.chatbi_semantic_package_dir.parts}
        if environment in formal_environments and "mock" in semantic_parts:
            raise ValueError("mcp/production cannot use the Mock Semantic Package")
        semantic_input_parts = {part.casefold() for part in self.chatbi_semantic_input_dir.parts}
        if environment in formal_environments and "mock" in semantic_input_parts:
            raise ValueError("mcp/production cannot compile the Mock semantic input")
        if environment in formal_environments and any(
            part.endswith("template") for part in semantic_parts | semantic_input_parts
        ):
            raise ValueError(
                "mcp/production cannot use internal-template directly; prepare and review "
                "semantic-input/internal first"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Load and cache validated application settings."""

    return AppSettings()


SETTINGS_MODEL_CONFIG = ConfigDict(extra="forbid", strict=True, frozen=True)
