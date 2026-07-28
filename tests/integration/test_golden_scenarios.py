from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    ("scenario_id", "question", "expected_status", "expected_tool"),
    [
        ("G01", "2026年7月一共有多少条记录？", "answered", "CountTool"),
        (
            "G02",
            "2026年7月各Channel的Failure Rate是多少？",
            "answered",
            "SearchIndexTool",
        ),
        ("G03", "SMS每天的发送记录趋势是什么？", "answered", "SearchIndexTool"),
        ("G04", "哪个Route的失败记录最多？", "answered", "SearchIndexTool"),
        ("G05", "比较SMS和Email的记录数量。", "answered", "SearchIndexTool"),
        (
            "G06",
            "2026年6月至8月的Failure Rate是多少？",
            "answered",
            "MsearchTool",
        ),
        (
            "G07",
            "2026年7月不存在的渠道有多少记录？空结果",
            "answered",
            "SearchIndexTool",
        ),
        ("G08", "2026年7月中国移动失败率是多少？", "not_answerable", None),
        ("G09", "2026年7月SLA是多少？", "not_answerable", None),
        ("G10", "请按不存在字段分组。", "not_answerable", None),
        ("G11", "请按消息正文分组。", "blocked", None),
        ("G12", "2026年9月一共有多少条记录？", "not_answerable", None),
    ],
)
def test_golden_questions_use_only_chat_api(
    client: TestClient,
    scenario_id: str,
    question: str,
    expected_status: str,
    expected_tool: str | None,
) -> None:
    response = client.post(
        "/api/chat",
        json={"session_id": f"golden-{scenario_id}", "message": question},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == expected_status
    if expected_tool is not None:
        assert payload["evidence"]["tool"] == expected_tool
        assert payload["evidence"]["query_dsl"]["queries"]
    else:
        assert payload["evidence"] is None


def test_g13_status_field_ambiguity_can_be_resolved_in_next_turn(
    client: TestClient,
) -> None:
    session_id = "golden-G13"
    first = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "2026年7月按状态分析记录分布。"},
    ).json()
    second = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "使用status。"},
    ).json()

    assert first["status"] == "needs_clarification"
    assert "statusCode" in first["assistant_message"]
    assert second["status"] == "answered"
    assert second["evidence"]["field_resolution"]["status"] == "status"
    assert second["chart"]["x_field"] == "status"


def test_g14_day_range_preserves_half_open_boundary(client: TestClient) -> None:
    payload = client.post(
        "/api/chat",
        json={
            "session_id": "golden-G14",
            "message": "2026年7月3日至2026年7月10日每天有多少记录？",
        },
    ).json()

    assert payload["status"] == "answered"
    time_range = payload["evidence"]["analysis_plan"]["time_range"]
    assert time_range["from"] == "2026-07-03T00:00:00+08:00"
    assert time_range["to"] == "2026-07-11T00:00:00+08:00"
    assert len(payload["table"]["rows"]) == 8


def test_g15_complex_request_uses_msearch_without_free_tool_loop(
    client: TestClient,
) -> None:
    payload = client.post(
        "/api/chat",
        json={
            "session_id": "golden-G15",
            "message": "2026年7月Failure Rate每日趋势，同时看Top Channel。",
        },
    ).json()

    assert payload["status"] == "answered"
    assert payload["evidence"]["tool"] == "MsearchTool"
    assert len(payload["evidence"]["query_plan"]["plans"]) == 2
    assert "ADDITIONAL_QUERY_RESULTS_AVAILABLE" in payload["warnings"]
