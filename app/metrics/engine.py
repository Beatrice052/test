from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict


class FailureRateValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    total_success_count: int
    total_failed_count: int
    other_count: int
    failure_rate: float | None


class MetricEngine:
    def failure_rate(
        self, total_count: int, success_count: int, failed_count: int
    ) -> FailureRateValues:
        other_count = total_count - success_count - failed_count
        rate: float | None
        if total_count == 0:
            rate = None
        else:
            raw = Decimal(100) * Decimal(failed_count) / Decimal(total_count)
            rate = float(raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        return FailureRateValues(
            total_count=total_count,
            total_success_count=success_count,
            total_failed_count=failed_count,
            other_count=other_count,
            failure_rate=rate,
        )
