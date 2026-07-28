from __future__ import annotations

from typing import Any

from app.results.models import QualityCheck, QualityReport, QualityStatus


class DataQA:
    def evaluate(
        self,
        payloads: list[dict[str, Any]],
        *,
        total_count: int,
        success_count: int | None = None,
        failed_count: int | None = None,
        bucket_total: int | None = None,
        failure_rate: float | None = None,
    ) -> QualityReport:
        checks = [
            QualityCheck(
                name="not_timed_out",
                passed=all(not bool(payload.get("timed_out")) for payload in payloads),
            ),
            QualityCheck(
                name="no_shard_failure",
                passed=all(
                    payload.get("_shards", {}).get("failed", 0) == 0 for payload in payloads
                ),
            ),
            QualityCheck(
                name="not_truncated",
                passed=all(
                    not bool(payload.get("_meta", {}).get("truncated")) for payload in payloads
                ),
            ),
            QualityCheck(name="count_non_negative", passed=total_count >= 0),
        ]
        if success_count is not None and failed_count is not None:
            other_count = total_count - success_count - failed_count
            checks.append(
                QualityCheck(
                    name="success_failed_other_reconcile",
                    passed=other_count >= 0
                    and success_count + failed_count + other_count == total_count,
                    detail=(
                        f"total={total_count}, success={success_count}, "
                        f"failed={failed_count}, other={other_count}"
                    ),
                )
            )
            checks.append(
                QualityCheck(
                    name="zero_denominator_is_null",
                    passed=total_count != 0 or failure_rate is None,
                )
            )
        if bucket_total is not None:
            checks.append(
                QualityCheck(
                    name="bucket_total_reconciles",
                    passed=bucket_total == total_count,
                    detail=f"buckets={bucket_total}, total={total_count}",
                )
            )
        status = (
            QualityStatus.PASSED if all(check.passed for check in checks) else QualityStatus.FAILED
        )
        return QualityReport(status=status, checks=checks)
