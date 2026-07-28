from __future__ import annotations

from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.gateway.models import GatewayFault
from app.main import create_app


def test_count_runs_through_api_and_selects_count_tool(client: TestClient) -> None:
    response = client.post(
        "/api/chat",
        json={"session_id": "session-count", "message": "2026年7月一共有多少条记录？"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "answered"
    assert payload["kpis"][0]["id"] == "total_count"
    assert payload["kpis"][0]["value"] == 186
    assert payload["table"] is None
    assert payload["chart"] is None
    assert payload["evidence"]["tool"] == "CountTool"
    assert payload["evidence"]["tool_reason_code"] == "PURE_COUNT"


def test_failure_rate_by_channel_returns_deterministic_components(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/chat",
        json={
            "session_id": "session-rate",
            "message": "2026年7月各Channel的Failure Rate是多少？",
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "answered"
    assert payload["metric_definition"] == {
        "metric_id": "failure_rate",
        "metric_version": "failure_rate.v1",
        "status": "POC_DEFINED",
    }
    assert payload["chart"]["type"] == "bar"
    assert payload["chart"]["x_field"] == "channel"
    assert payload["chart"]["y_field"] == "failure_rate"
    assert len(payload["table"]["rows"]) == 3
    assert payload["evidence"]["tool"] == "SearchIndexTool"
    assert payload["evidence"]["qa"]["status"] == "PASSED"
    query = payload["evidence"]["query_dsl"]["queries"][0]["body"]
    assert query["aggs"]["primary_group"]["aggs"]["failed"]["filter"]["terms"]["status"] == [
        "FAILED",
        "ACKFAIL",
    ]


def test_cross_month_query_uses_msearch_and_merges_before_metric(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/chat",
        json={
            "session_id": "session-multi",
            "message": "2026年6月至8月的Failure Rate是多少？",
        },
    )

    payload = response.json()
    assert payload["status"] == "answered"
    assert payload["evidence"]["tool"] == "MsearchTool"
    assert len(payload["evidence"]["query_dsl"]["queries"]) == 3
    kpis = {item["id"]: item["value"] for item in payload["kpis"]}
    assert kpis["total_count"] == 552
    assert kpis["failure_rate"] == 33.33


def test_ambiguous_question_and_follow_up_share_pending_state(
    client: TestClient,
) -> None:
    session_id = "session-clarify"
    first = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "看看最近的失败情况。"},
    ).json()
    second = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "按Channel。"},
    ).json()

    assert first["status"] == "needs_clarification"
    assert first["needs_clarification"] is True
    assert "Channel" in first["clarification_question"]
    assert second["status"] == "answered"
    assert second["evidence"]["field_resolution"]["channel"] == "channel"
    assert second["kpis"][0]["value"] == 62
    assert len(second["table"]["rows"]) == 3


def test_session_reset_removes_pending_clarification(client: TestClient) -> None:
    session_id = "session-reset-pending"
    client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "看看最近的失败情况。"},
    )
    client.post("/api/session/reset", json={"session_id": session_id})
    response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "按Channel。"},
    )

    assert response.json()["status"] == "answered"
    assert response.json()["evidence"]["analysis_plan"]["analysis_type"] == "terms_breakdown"


def test_policy_block_hides_sensitive_field_from_entire_response(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/chat",
        json={"session_id": "session-policy", "message": "请按消息正文分组。"},
    )

    payload = response.json()
    serialized = response.text
    assert payload["status"] == "blocked"
    assert payload["reason_code"] == "POLICY_BLOCKED"
    assert payload["evidence"] is None
    assert "messageBody" not in serialized
    assert "customerName" not in serialized


def test_no_data_has_null_rate_and_no_misleading_chart(client: TestClient) -> None:
    response = client.post(
        "/api/chat",
        json={
            "session_id": "session-empty",
            "message": "2026年7月不存在的渠道的Failure Rate是多少？空结果",
        },
    )

    payload = response.json()
    assert payload["status"] == "answered"
    assert payload["assistant_message"] == "当前条件下没有数据。"
    kpis = {item["id"]: item["value"] for item in payload["kpis"]}
    assert kpis["total_count"] == 0
    assert kpis["failure_rate"] is None
    assert payload["chart"] is None


def test_data_qa_failure_suppresses_business_answer(settings: Settings) -> None:
    with TestClient(create_app(settings, gateway_fault=GatewayFault.QUERY_TIMEOUT)) as client:
        response = client.post(
            "/api/chat",
            json={
                "session_id": "session-timeout",
                "message": "2026年7月各Channel的Failure Rate是多少？",
            },
        )

    payload = response.json()
    assert payload["status"] == "error"
    assert payload["reason_code"] == "DATA_QUALITY_FAILED"
    assert payload["kpis"] == []
    assert payload["table"] is None
    assert payload["chart"] is None
    assert payload["evidence"]["qa"]["status"] == "FAILED"
