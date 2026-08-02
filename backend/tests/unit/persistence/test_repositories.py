"""Ownership, idempotency, locking, and atomic snapshot persistence."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.analytics.bundle import DatasetBundleBuilder
from app.contracts.analysis import AnswerStatus, TurnKind
from app.contracts.common import Provenance, semantic_hash
from app.contracts.request import ChatRequest
from app.contracts.session import ActiveAnalyticalContext, AnswerSnapshot
from app.persistence.answer_repository import AnswerRepository
from app.persistence.database import Database
from app.persistence.errors import (
    IdempotencyConflict,
    OwnedObjectNotFound,
    SessionLockConflict,
    TurnCancelled,
    VersionConflict,
)
from app.persistence.idempotency_repository import IdempotencyRepository
from app.persistence.locks import SessionLockRepository
from app.persistence.session_repository import SessionRepository
from tests.unit.analytics.test_metric_qa import _derive


@pytest.fixture
def database() -> Database:
    value = Database("sqlite:///:memory:")
    value.create_schema()
    yield value
    value.dispose()


def _request(session_id: str, *, message: str = "查询7月消息记录") -> ChatRequest:
    return ChatRequest(
        session_id=session_id,
        message=message,
        client_turn_id="client-turn-0001",
    )


def _answer(session_id: str, answer_id: str = "ans_test") -> AnswerSnapshot:
    now = datetime(2026, 8, 1, tzinfo=UTC)
    payload = {
        "session_id": session_id,
        "status": AnswerStatus.CLARIFICATION_REQUIRED,
        "semantic_package_version": "sp_mock",
    }
    return AnswerSnapshot(
        object_id=answer_id,
        created_at=now,
        content_hash=semantic_hash(payload),
        provenance=Provenance(producer="tests.persistence"),
        session_id=session_id,
        turn_kind=TurnKind.NEW_ANALYSIS,
        status=AnswerStatus.CLARIFICATION_REQUIRED,
        semantic_package_version="sp_mock",
        metric_versions=(),
        limitations=("需要澄清",),
    )


def test_session_ownership_and_optimistic_version(database: Database) -> None:
    repository = SessionRepository(database)
    created = repository.create_session("subject-a", title="渠道质量")

    assert repository.get_session("subject-a", created.object_id).title == "渠道质量"
    with pytest.raises(OwnedObjectNotFound):
        repository.get_session("subject-b", created.object_id)

    updated = repository.update_title(
        "subject-a", created.object_id, title="失败分析", expected_version=0
    )
    assert updated.version == 1
    with pytest.raises(VersionConflict):
        repository.update_title(
            "subject-a", created.object_id, title="过期写入", expected_version=0
        )


def test_idempotency_replay_conflict_and_retry(database: Database) -> None:
    sessions = SessionRepository(database)
    session = sessions.create_session("subject-a")
    repository = IdempotencyRepository(database)
    request = _request(session.object_id)

    started = repository.begin("subject-a", session.object_id, request)
    running = repository.begin("subject-a", session.object_id, request)
    assert started.outcome == "STARTED"
    assert running.outcome == "RUNNING"
    assert running.turn_id == started.turn_id

    conflicting = request.model_copy(update={"message": "同 key 的不同请求"})
    with pytest.raises(IdempotencyConflict):
        repository.begin("subject-a", session.object_id, conflicting)

    repository.mark_failed("subject-a", started.turn_id, retryable=True)
    retried = repository.begin("subject-a", session.object_id, request)
    assert retried.outcome == "STARTED"
    assert retried.attempt == 2
    assert retried.turn_id != started.turn_id


def test_session_lock_lease_and_owner(database: Database) -> None:
    session = SessionRepository(database).create_session("subject-a")
    locks = SessionLockRepository(database)

    locks.acquire("subject-a", session.object_id, "trn_one")
    locks.heartbeat("subject-a", session.object_id, "trn_one")
    with pytest.raises(SessionLockConflict):
        locks.acquire("subject-a", session.object_id, "trn_two")
    assert not locks.release("subject-a", session.object_id, "trn_wrong")
    assert locks.release("subject-a", session.object_id, "trn_one")

    locks.acquire("subject-a", session.object_id, "trn_expired", lease_seconds=0)
    assert locks.release_expired() == 1
    locks.acquire("subject-a", session.object_id, "trn_recovered")


def test_answer_completion_is_atomic_and_replayable(database: Database) -> None:
    sessions = SessionRepository(database)
    session = sessions.create_session("subject-a")
    idempotency = IdempotencyRepository(database)
    request = _request(session.object_id)
    claim = idempotency.begin("subject-a", session.object_id, request)
    snapshot = _answer(session.object_id)
    active_context = ActiveAnalyticalContext(
        analytical_base_answer_id=snapshot.object_id,
        dataset_ids=("sub_message",),
        time_summary="2026-07",
    )

    answers = AnswerRepository(database)
    answers.persist_answer("subject-a", claim.turn_id, snapshot, active_context)

    replay = idempotency.begin("subject-a", session.object_id, request)
    assert replay.outcome == "COMPLETED"
    assert replay.answer_id == snapshot.object_id
    assert answers.get_answer("subject-a", snapshot.object_id) == snapshot
    assert sessions.get_session("subject-a", session.object_id).active_context == active_context
    with pytest.raises(OwnedObjectNotFound):
        answers.get_answer("subject-b", snapshot.object_id)


def test_immutable_dataset_object_reference_survives_later_logical_id_reuse(
    database: Database,
) -> None:
    sessions = SessionRepository(database)
    session = sessions.create_session("subject-a")
    idempotency = IdempotencyRepository(database)
    answers = AnswerRepository(database)
    first_dataset = _derive().dataset
    second_dataset = first_dataset.model_copy(
        update={
            "object_id": "ds_channel_metrics_second",
            "content_hash": semantic_hash({"version": 2}),
            "rows": first_dataset.rows[:1],
        }
    )
    context = ActiveAnalyticalContext(dataset_ids=("sub_message",))

    for index, dataset in enumerate((first_dataset, second_dataset), start=1):
        request = _request(session.object_id).model_copy(
            update={"client_turn_id": f"dataset-collision-{index}"}
        )
        claim = idempotency.begin("subject-a", session.object_id, request)
        snapshot = _answer(session.object_id, f"ans_dataset_collision_{index}").model_copy(
            update={"dataset_bundle": DatasetBundleBuilder().build((dataset,))}
        )
        answers.persist_answer("subject-a", claim.turn_id, snapshot, context)

    # The reusable logical name is intentionally not used as a public address. Immutable
    # object references published by Dashboard/Evidence remain answer-stable.
    assert answers.get_dataset("subject-a", first_dataset.object_id) == first_dataset
    assert answers.get_dataset("subject-a", second_dataset.object_id) == second_dataset
    with pytest.raises(OwnedObjectNotFound):
        answers.get_dataset("subject-a", first_dataset.dataset_id)


def test_cancelled_turn_cannot_advance_checkpoint_or_publish_answer(database: Database) -> None:
    sessions = SessionRepository(database)
    session = sessions.create_session("subject-a")
    claim = IdempotencyRepository(database).begin(
        "subject-a", session.object_id, _request(session.object_id)
    )

    sessions.cancel_turn("subject-a", claim.turn_id)

    with pytest.raises(TurnCancelled):
        sessions.save_safe_state(
            "subject-a",
            claim.turn_id,
            {"node": "produce_answer", "terminal_status": "COMPLETED"},
        )
    with pytest.raises(TurnCancelled):
        AnswerRepository(database).persist_answer(
            "subject-a",
            claim.turn_id,
            _answer(session.object_id),
            ActiveAnalyticalContext(),
        )
    sessions.mark_turn_failed(
        "subject-a", claim.turn_id, error={"code": "late_failure"}, retryable=False
    )
    assert sessions.get_turn("subject-a", claim.turn_id).status == "CANCELLED"
