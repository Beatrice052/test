from __future__ import annotations

from fastapi.testclient import TestClient


def test_home_page_contains_chat_shell_and_mock_disclosure(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert "OpenSearch ChatBI POC" in html
    assert "MOCK DATA" in html
    assert "Mock OpenSearch" in html
    assert "tbl_os_sub_message_2026_07" in html
    assert "Asia/Hong_Kong" in html
    assert "清空会话" in html
    assert "message-input" in html
    assert "看看最近的失败情况。" in html
    assert "/static/css/app.css" in html
    assert "/static/vendor/echarts.min.js" in html
    assert "/static/js/app.js" in html
    assert "https://" not in html
    assert "cdn." not in html.lower()
    assert "unpkg" not in html.lower()
    assert "jsdelivr" not in html.lower()


def test_local_static_assets_are_served(client: TestClient) -> None:
    css = client.get("/static/css/app.css")
    javascript = client.get("/static/js/app.js")
    echarts = client.get("/static/vendor/echarts.min.js")

    assert css.status_code == 200
    assert "--teal" in css.text
    assert javascript.status_code == 200
    assert 'fetch("/api/chat"' in javascript.text
    assert 'dataset.chatbiReady = "true"' in javascript.text
    assert "cdn" not in javascript.text.lower()
    assert echarts.status_code == 200
    assert len(echarts.content) > 1_000_000
