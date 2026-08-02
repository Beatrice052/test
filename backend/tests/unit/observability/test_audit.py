"""Audit records are useful for operations and exclude sensitive model payloads."""

import json
import logging
from typing import Any

import pytest

from app.contracts.common import StrictModel
from app.observability.audit import AuditedLLMClient, SafeAuditLogger


class ProbeOutput(StrictModel):
    ok: bool


class ProbeClient:
    async def generate(self, **kwargs: Any) -> ProbeOutput:
        del kwargs
        return ProbeOutput(ok=True)


@pytest.mark.asyncio
async def test_llm_audit_logs_only_allowlisted_metadata(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tests.chatbi.audit")
    audited = AuditedLLMClient(
        ProbeClient(),  # type: ignore[arg-type]
        adapter_name="probe",
        model_identifier="approved-model-v1",
        audit=SafeAuditLogger(logger),
    )
    with caplog.at_level(logging.INFO, logger=logger.name):
        result = await audited.generate(
            operation="turn_and_analysis_plan",
            system_prompt="do not log this system prompt",
            input_payload={"api_key": "super-secret", "rows": [{"customer": "private"}]},
            output_schema=ProbeOutput,
            timeout_seconds=1,
            correlation_id="cor_safe_audit",
        )

    assert result.ok
    record = json.loads(caplog.records[-1].message)
    assert record["operation"] == "turn_and_analysis_plan"
    assert record["schema_validation"] == "passed"
    assert record["model"] == "approved-model-v1"
    serialized = caplog.records[-1].message
    assert "super-secret" not in serialized
    assert "private" not in serialized
    assert "system prompt" not in serialized
