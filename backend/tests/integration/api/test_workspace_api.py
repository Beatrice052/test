"""Full owner-scoped workspace API restores immutable answer artifacts."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.semantic.package import CompiledSemanticPackage
from app.settings import AppSettings

ROOT = Path(__file__).parents[3]
PACKAGE_DIR = ROOT.parent / "compiled-semantic" / "mock"


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        app_database_url=f"sqlite:///{(tmp_path / 'chatbi.db').as_posix()}",
        app_checkpoint_path=tmp_path / "checkpoints.db",
        app_artifact_dir=tmp_path / "artifacts",
        chatbi_semantic_package_dir=PACKAGE_DIR,
        chatbi_llm_mode="rule_based",
        chatbi_gateway_mode="mock",
    )


def test_session_chat_answer_dataset_evidence_and_ownership(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    owner = {"x-mock-subject": "owner-a", "x-mock-roles": "business"}
    analyst = {"x-mock-subject": "owner-a", "x-mock-roles": "analyst"}
    other = {"x-mock-subject": "owner-b", "x-mock-roles": "analyst"}
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/sessions", json={"title": "July channel review"}, headers=owner
        )
        assert created.status_code == 201
        session = created.json()
        session_id = session["object_id"]

        chat = client.post(
            "/api/v1/chat",
            json={
                "session_id": session_id,
                "message": "查询2026年7月各Channel失败率",
                "client_turn_id": "api-workspace-turn-0001",
                "mode": "standard",
            },
            headers=owner,
        )
        assert chat.status_code == 200
        response = chat.json()
        assert response["status"] == "COMPLETED"
        answer = response["answer"]
        answer_id = answer["object_id"]
        assert answer["dashboard_spec"]["blocks"]
        assert answer["evidence_package"] is not None

        replay = client.post(
            "/api/v1/chat",
            json={
                "session_id": session_id,
                "message": "查询2026年7月各Channel失败率",
                "client_turn_id": "api-workspace-turn-0001",
                "mode": "standard",
            },
            headers=owner,
        )
        assert replay.json()["answer"]["object_id"] == answer_id

        detail = client.get(f"/api/v1/sessions/{session_id}", headers=owner)
        assert detail.status_code == 200
        assert [item["object_id"] for item in detail.json()["answers"]] == [answer_id]
        turn = client.get(f"/api/v1/turns/{response['turn_id']}", headers=owner)
        assert turn.json()["status"] == "COMPLETED"

        business_evidence = client.get(f"/api/v1/answers/{answer_id}/evidence", headers=owner)
        assert business_evidence.status_code == 200
        assert business_evidence.json()["advanced"] is None
        advanced_evidence = client.get(f"/api/v1/answers/{answer_id}/evidence", headers=analyst)
        assert advanced_evidence.json()["advanced"]["compiled_queries"]

        dataset = answer["dataset_bundle"]["datasets"][-1]
        dataset_object_id = dataset["object_id"]
        rows = client.get(
            f"/api/v1/datasets/{dataset_object_id}/rows?offset=0&limit=2",
            headers=owner,
        )
        assert rows.status_code == 200
        assert len(rows.json()["rows"]) == 2
        assert rows.json()["total"] >= 2
        exported = client.get(f"/api/v1/datasets/{dataset_object_id}/csv", headers=owner)
        assert exported.status_code == 200
        assert exported.text.startswith("row_id,")
        assert "attachment" in exported.headers["content-disposition"]

        assert client.get(f"/api/v1/sessions/{session_id}", headers=other).status_code == 404
        assert client.get(f"/api/v1/answers/{answer_id}", headers=other).status_code == 404
        assert (
            client.get(f"/api/v1/datasets/{dataset_object_id}/rows", headers=other).status_code
            == 404
        )

        semantic = client.get("/api/v1/semantic/packages/current", headers=owner)
        assert semantic.status_code == 200
        assert (
            semantic.json()["package_version"]
            == CompiledSemanticPackage(PACKAGE_DIR).manifest.package_version
        )
        assert client.get(f"/api/v1/answers/{answer_id}/debug", headers=other).status_code == 404


def test_session_version_archive_conflict_and_raw_dsl_rejection(tmp_path: Path) -> None:
    owner = {"x-mock-subject": "owner-a", "x-mock-roles": "analyst"}
    with TestClient(create_app(_settings(tmp_path))) as client:
        session = client.post("/api/v1/sessions", json={}, headers=owner).json()
        session_id = session["object_id"]
        renamed = client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"title": "Renamed", "expected_version": 0},
            headers=owner,
        )
        assert renamed.status_code == 200
        assert renamed.json()["title"] == "Renamed"
        conflict = client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"title": "Stale", "expected_version": 0},
            headers=owner,
        )
        assert conflict.status_code == 409
        archived = client.post(f"/api/v1/sessions/{session_id}/archive", headers=owner)
        assert archived.json()["archived"] is True
        blocked = client.post(
            "/api/v1/chat",
            json={
                "session_id": session_id,
                "message": "查询2026年7月消息记录数",
                "client_turn_id": "api-archived-turn-0001",
            },
            headers=owner,
        )
        assert blocked.status_code == 409
        raw_dsl = client.post(
            "/api/v1/chat",
            json={
                "session_id": None,
                "message": "run raw DSL",
                "client_turn_id": "api-raw-dsl-turn-0001",
                "raw_dsl": {"match_all": {}},
            },
            headers=owner,
        )
        assert raw_dsl.status_code == 422


def test_chat_stream_follows_real_graph_nodes_and_returns_result(tmp_path: Path) -> None:
    owner = {"x-mock-subject": "owner-a", "x-mock-roles": "business"}
    with TestClient(create_app(_settings(tmp_path))) as client:
        session = client.post("/api/v1/sessions", json={}, headers=owner).json()
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={
                "session_id": session["object_id"],
                "message": "分析2026年7月各Channel消息量",
                "client_turn_id": "api-stream-turn-0001",
                "mode": "standard",
            },
            headers=owner,
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            payloads = [
                json.loads(line.removeprefix("data: "))
                for line in response.iter_lines()
                if line.startswith("data: ")
            ]

    progress = [item["progress"] for item in payloads if item["event"] == "progress"]
    stages = [item["stage"] for item in progress]
    titles = [item["title"] for item in progress]
    expected = ["intent", "query_plan", "dsl", "search", "analytics", "dashboard", "complete"]
    assert [stages.index(stage) for stage in expected] == sorted(
        stages.index(stage) for stage in expected
    )
    assert [item["sequence"] for item in progress] == list(range(1, len(progress) + 1))
    assert "Agent A 已完成意图识别" in titles
    assert "Agent B 已生成逻辑 QueryPlan" in titles

    serialized_progress = json.dumps(progress, ensure_ascii=False)
    assert "query_dsl" not in serialized_progress
    assert "system_prompt" not in serialized_progress
    assert "chain_of_thought" not in serialized_progress
    assert "api_key" not in serialized_progress

    results = [item["result"] for item in payloads if item["event"] == "result"]
    assert len(results) == 1
    assert results[0]["status"] == "COMPLETED"
    assert results[0]["answer"]["dashboard_spec"]["blocks"]
