from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QualityStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"


class QualityCheck(ResultModel):
    name: str
    passed: bool
    detail: str | None = None


class QualityReport(ResultModel):
    status: QualityStatus
    checks: list[QualityCheck] = Field(default_factory=list)


class PreparedData(ResultModel):
    columns: list[dict[str, str]] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    totals: dict[str, Any] = Field(default_factory=dict)
    quality: QualityReport
    provenance: dict[str, Any] = Field(default_factory=dict)


class ChartSpec(ResultModel):
    type: str
    title: str
    x_field: str
    y_field: str
    series_field: str | None = None
    data: list[dict[str, Any]] = Field(default_factory=list)


class ProcessedResult(ResultModel):
    prepared_data: PreparedData
    chart: ChartSpec | None = None
    warnings: list[str] = Field(default_factory=list)
    raw_result_summary: dict[str, Any] = Field(default_factory=dict)
