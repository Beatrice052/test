"""Gateway retry policy and immutable ExecutionRecord creation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from app.contracts.common import Provenance, semantic_hash
from app.contracts.execution import ExecutionRecord, RawSearchResult
from app.contracts.query import CompiledQuery, QueryStepStatus
from app.gateway.base import OpenSearchGateway
from app.gateway.errors import GatewayError
from app.observability.audit import SafeAuditLogger
from app.persistence.ids import new_id


@dataclass(frozen=True, slots=True)
class GatewayExecution:
    record: ExecutionRecord
    result: RawSearchResult | None


class GatewayExecutor:
    def __init__(
        self,
        gateway: OpenSearchGateway,
        *,
        mode: Literal["mock", "mcp", "direct"],
        max_attempts: int = 2,
        audit: SafeAuditLogger | None = None,
    ) -> None:
        if max_attempts < 1 or max_attempts > 3:
            raise ValueError("max_attempts must be between 1 and 3")
        self.gateway = gateway
        self.mode = mode
        self.max_attempts = max_attempts
        self.audit = audit or SafeAuditLogger()

    async def execute(self, query: CompiledQuery) -> GatewayExecution:
        started_at = datetime.now(UTC)
        attempt = 0
        while attempt < self.max_attempts:
            attempt += 1
            try:
                result = await self.gateway.execute_search(query)
            except GatewayError as error:
                if error.retryable and attempt < self.max_attempts:
                    continue
                record = self._record(
                    query=query,
                    started_at=started_at,
                    attempt=attempt,
                    status=QueryStepStatus.FAILED,
                    error_code=error.code,
                    retryable=error.retryable,
                )
                self._audit_record(record)
                return GatewayExecution(
                    record=record,
                    result=None,
                )
            record = self._record(
                query=query,
                started_at=started_at,
                attempt=attempt,
                status=QueryStepStatus.SUCCEEDED,
                result=result,
            )
            self._audit_record(record)
            return GatewayExecution(
                record=record,
                result=result,
            )
        raise AssertionError("unreachable retry loop")

    def _record(
        self,
        *,
        query: CompiledQuery,
        started_at: datetime,
        attempt: int,
        status: QueryStepStatus,
        result: RawSearchResult | None = None,
        error_code: str | None = None,
        retryable: bool = False,
    ) -> ExecutionRecord:
        completed_at = datetime.now(UTC)
        raw_hash = semantic_hash(result) if result is not None else None
        payload = {
            "query_id": query.object_id,
            "query_fingerprint": query.query_fingerprint,
            "status": status,
            "attempt": attempt,
            "raw_result_hash": raw_hash,
            "error_code": error_code,
        }
        return ExecutionRecord(
            object_id=new_id("exe"),
            created_at=started_at,
            content_hash=semantic_hash(payload),
            provenance=Provenance(
                producer="gateway.executor",
                source_ids=(query.object_id,),
            ),
            query_id=query.object_id,
            query_fingerprint=query.query_fingerprint,
            step_id=query.step_id,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            attempt=attempt,
            raw_result_hash=raw_hash,
            timed_out=result.timed_out if result is not None else error_code == "GW_TIMEOUT",
            shard_failures=result.shards.failed if result is not None else 0,
            error_code=error_code,
            retryable=retryable,
            gateway_mode=self.mode,
        )

    def _audit_record(self, record: ExecutionRecord) -> None:
        completed_at = record.completed_at or record.started_at
        duration = (completed_at - record.started_at).total_seconds() * 1000
        self.audit.emit(
            "gateway_call",
            gateway_mode=self.mode,
            step_id=record.step_id,
            status=record.status.value.casefold(),
            attempt=record.attempt,
            duration_ms=round(duration, 3),
        )
