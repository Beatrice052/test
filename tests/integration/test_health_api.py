from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_reports_complete_mock_capabilities_without_secrets(
    client: TestClient,
) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["phase"] == "external-mock-complete"
    assert payload["data_source_mode"] == "mock"
    assert payload["connection_status"] == "mock"
    assert payload["index_scope"] == "tbl_os_sub_message_YYYY_MM"
    assert payload["business_timezone"] == "Asia/Hong_Kong"
    assert payload["semantic_model_version"] == "mock-semantic.v1"
    assert payload["capabilities"]["semantic_compiler"] is True
    assert payload["capabilities"]["query_execution"] is True
    assert payload["capabilities"]["generic_opensearch_api"] is False
    assert payload["capabilities"]["ppl"] is False
    assert "token" not in str(payload).lower()
    assert "password" not in str(payload).lower()


def test_semantic_report_exposes_import_quality_not_sensitive_values(
    client: TestClient,
) -> None:
    response = client.get("/api/admin/semantic/report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_version"] == "mock-semantic.v1"
    assert payload["import_status"] == "PASSED_WITH_WARNINGS"
    assert payload["report"]["ignored_columns"] == ["candidate_role"]
    assert "candidate_role" not in str(payload["report"]["source_summary"])


def test_session_reset_is_scoped_and_typed(client: TestClient) -> None:
    response = client.post("/api/session/reset", json={"session_id": "session-001"})

    assert response.status_code == 200
    assert response.json() == {"session_id": "session-001", "status": "reset"}


def test_chat_request_validation_rejects_blank_message(client: TestClient) -> None:
    response = client.post(
        "/api/chat",
        json={"session_id": "session-001", "message": "   "},
    )

    assert response.status_code == 422
