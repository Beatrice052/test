"""A new process/container instance can inspect pending and failed turns."""

from pathlib import Path

from app.contracts.request import ChatRequest
from app.persistence.database import Database
from app.persistence.idempotency_repository import IdempotencyRepository
from app.persistence.ids import uuid7
from app.persistence.session_repository import SessionRepository


def test_file_database_restores_safe_pending_and_failed_state() -> None:
    database_path = Path(".cache") / f"recovery-{uuid7()}.db"
    database_path.parent.mkdir(exist_ok=True)
    database_url = f"sqlite:///{database_path.as_posix()}"
    try:
        first_database = Database(database_url)
        first_database.create_schema()
        first_sessions = SessionRepository(first_database)
        session = first_sessions.create_session("subject-a")
        request = ChatRequest(
            session_id=session.object_id,
            message="查询7月失败情况",
            client_turn_id="restart-turn-0001",
        )
        claim = IdempotencyRepository(first_database).begin("subject-a", session.object_id, request)
        first_sessions.save_safe_state(
            "subject-a",
            claim.turn_id,
            {
                "node": "analyst_planner",
                "semantic_package_version": "sp_mock",
                "candidate_ids": ["sub_message", "failure_rate.v1"],
            },
        )
        first_sessions.mark_turn_failed(
            "subject-a",
            claim.turn_id,
            error={"code": "LLM_TEMPORARY"},
            retryable=True,
        )
        IdempotencyRepository(first_database).mark_failed(
            "subject-a", claim.turn_id, retryable=True
        )
        pending_request = ChatRequest(
            session_id=session.object_id,
            message="查询7月消息记录",
            client_turn_id="restart-turn-0002",
        )
        pending_claim = IdempotencyRepository(first_database).begin(
            "subject-a", session.object_id, pending_request
        )
        first_sessions.save_safe_state(
            "subject-a",
            pending_claim.turn_id,
            {
                "node": "retrieve_semantic_candidates",
                "semantic_package_version": "sp_mock",
            },
        )
        first_database.dispose()

        restarted_database = Database(database_url)
        restarted_sessions = SessionRepository(restarted_database)
        recovered = restarted_sessions.recoverable_turns("subject-a")
        assert len(recovered) == 2
        by_turn_id = {turn.turn_id: turn for turn in recovered}
        assert by_turn_id[claim.turn_id].status == "FAILED"
        assert by_turn_id[pending_claim.turn_id].status == "RUNNING"
        assert restarted_sessions.safe_state_from_turn(by_turn_id[claim.turn_id]) == {
            "node": "analyst_planner",
            "semantic_package_version": "sp_mock",
            "candidate_ids": ["sub_message", "failure_rate.v1"],
        }
        assert restarted_sessions.safe_state_from_turn(by_turn_id[pending_claim.turn_id]) == {
            "node": "retrieve_semantic_candidates",
            "semantic_package_version": "sp_mock",
        }
        assert restarted_sessions.request_from_turn(by_turn_id[claim.turn_id]) == request
        assert (
            restarted_sessions.request_from_turn(by_turn_id[pending_claim.turn_id])
            == pending_request
        )
        assert restarted_sessions.recoverable_turns("subject-b") == ()
        restarted_database.dispose()
    finally:
        database_path.unlink(missing_ok=True)
