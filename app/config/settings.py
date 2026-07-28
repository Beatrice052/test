from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central runtime settings.

    Time and monthly-index rules are deliberately centralized here so later
    semantic and query modules do not depend on server-local defaults.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CHATBI_",
        extra="ignore",
    )

    app_name: str = "OpenSearch ChatBI POC"
    app_env: Literal["development", "test", "production"] = "development"
    data_source_mode: Literal["mock", "mcp"] = "mock"
    intent_backend: Literal["mock", "structured_llm"] = "mock"
    index_pattern: str = "tbl_os_sub_message_{yyyy}_{mm}"
    business_timezone: str = "Asia/Hong_Kong"
    default_time_from: datetime = datetime.fromisoformat("2026-07-01T00:00:00+08:00")
    default_time_to: datetime = datetime.fromisoformat("2026-08-01T00:00:00+08:00")
    semantic_model_version: str = "mock-semantic.v1"
    llm_timeout_seconds: int = Field(default=30, gt=0, le=300)
    session_ttl_seconds: int = Field(default=1800, gt=0)
    session_capacity: int = Field(default=200, gt=0)
    session_max_messages: int = Field(default=30, gt=1)
    max_message_chars: int = Field(default=2000, ge=1, le=20_000)

    @model_validator(mode="after")
    def validate_runtime_contract(self) -> Settings:
        if "{yyyy}" not in self.index_pattern or "{mm}" not in self.index_pattern:
            raise ValueError("index_pattern must contain {yyyy} and {mm}")

        try:
            ZoneInfo(self.business_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown business timezone: {self.business_timezone}") from exc

        if self.default_time_from.tzinfo is None or self.default_time_to.tzinfo is None:
            raise ValueError("default time range must be timezone-aware")
        if self.default_time_from >= self.default_time_to:
            raise ValueError("default_time_from must be earlier than default_time_to")
        return self

    @property
    def index_scope_label(self) -> str:
        return self.index_pattern.replace("{yyyy}", "YYYY").replace("{mm}", "MM")

    @property
    def default_time_range_label(self) -> str:
        return (
            f"{self.default_time_from.isoformat()} — {self.default_time_to.isoformat()} (左闭右开)"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
