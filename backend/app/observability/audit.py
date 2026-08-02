"""Allowlisted audit logging that never records prompts, rows, DSL, endpoints, or secrets."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from time import perf_counter

from app.llm.client import OutputModel, StructuredLLMClient

_ALLOWED_FIELDS = frozenset(
    {
        "adapter",
        "attempt",
        "correlation_id",
        "duration_ms",
        "error_type",
        "event",
        "gateway_mode",
        "model",
        "operation",
        "schema_validation",
        "session_id",
        "status",
        "step_id",
        "timestamp",
        "turn_id",
    }
)


class SafeAuditLogger:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger("chatbi.audit")

    def emit(self, event: str, **fields: object) -> None:
        record = {
            "event": event,
            "timestamp": datetime.now(UTC).isoformat(),
            **{key: value for key, value in fields.items() if key in _ALLOWED_FIELDS},
        }
        self.logger.info(json.dumps(record, ensure_ascii=False, sort_keys=True))


class AuditedLLMClient:
    """Decorate the single structured LLM interface without observing its payload."""

    def __init__(
        self,
        delegate: StructuredLLMClient,
        *,
        adapter_name: str,
        model_identifier: str | None = None,
        audit: SafeAuditLogger,
    ) -> None:
        self.delegate = delegate
        self.adapter_name = adapter_name
        self.model_identifier = model_identifier
        self.audit = audit

    async def generate(
        self,
        *,
        operation: str,
        system_prompt: str,
        input_payload: dict[str, object],
        output_schema: type[OutputModel],
        timeout_seconds: float,
        correlation_id: str,
    ) -> OutputModel:
        started = perf_counter()
        try:
            result = await self.delegate.generate(
                operation=operation,
                system_prompt=system_prompt,
                input_payload=input_payload,
                output_schema=output_schema,
                timeout_seconds=timeout_seconds,
                correlation_id=correlation_id,
            )
        except BaseException as error:
            self.audit.emit(
                "llm_call",
                adapter=self.adapter_name,
                correlation_id=correlation_id,
                operation=operation,
                model=self.model_identifier,
                status="failed",
                schema_validation="failed",
                duration_ms=round((perf_counter() - started) * 1000, 3),
                error_type=type(error).__name__,
            )
            raise
        self.audit.emit(
            "llm_call",
            adapter=self.adapter_name,
            correlation_id=correlation_id,
            operation=operation,
            model=self.model_identifier,
            status="succeeded",
            schema_validation="passed",
            duration_ms=round((perf_counter() - started) * 1000, 3),
        )
        return result
