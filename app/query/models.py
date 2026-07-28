from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class QueryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Complexity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class CompiledQuery(QueryModel):
    query_id: str
    logical_query_id: str
    language: Literal["OPENSEARCH_DSL"] = "OPENSEARCH_DSL"
    index: str
    query_type: str
    body: dict[str, Any]
    read_only: bool = True
    estimated_complexity: Complexity
    validation_status: Literal["PENDING", "PASSED"] = "PENDING"


class ValidationCheck(QueryModel):
    name: str
    passed: bool
    detail: str | None = None


class ValidationResult(QueryModel):
    status: Literal["PASSED", "FAILED"]
    checks: list[ValidationCheck] = Field(default_factory=list)
    estimated_complexity: Complexity


class IndexResolution(QueryModel):
    indices: list[str]
    missing_indices: list[str] = Field(default_factory=list)
