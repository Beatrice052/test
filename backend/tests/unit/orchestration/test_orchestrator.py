"""Turn-level timeout and cancellation are persistence boundaries, not UI hints."""

import asyncio
from typing import cast

import pytest

from app.contracts.request import ChatRequest, IdentityContext
from app.orchestration.graph import ChatBIGraph
from app.orchestration.orchestrator import ChatBIOrchestrator
from app.persistence.answer_repository import AnswerRepository
from app.persistence.database import Database
from app.persistence.idempotency_repository import IdempotencyRepository
from app.persistence.locks import SessionLockRepository
from app.persistence.session_repository import SessionRepository


class _SlowGraph:
    async def ainvoke(self, *_: object, **__: object) -> dict[str, object]:
        await asyncio.sleep(1)
        return {}


@pytest.mark.asyncio
async def test_turn_timeout_fails_retryably_without_publishing_answer() -> None:
    database = Database("sqlite:///:memory:")
    database.create_schema()
    sessions = SessionRepository(database)
    answers = AnswerRepository(database)
    idempotency = IdempotencyRepository(database)
    session = sessions.create_session("subject-a")
    request = ChatRequest(
        session_id=session.object_id,
        message="分析消息运行情况",
        client_turn_id="timeout-turn-0001",
    )
    orchestrator = ChatBIOrchestrator(
        graph=cast(ChatBIGraph, _SlowGraph()),
        sessions=sessions,
        answers=answers,
        idempotency=idempotency,
        locks=SessionLockRepository(database),
        turn_timeout_seconds=0.01,
    )

    result = await orchestrator.run(
        IdentityContext(subject_id="subject-a"),
        request,
        correlation_id="cor_timeout",
    )

    assert result.status == "FAILED"
    turn = sessions.get_turn("subject-a", result.turn_id)
    assert turn.status == "FAILED"
    assert turn.retryable is True
    assert answers.list_answers("subject-a", session.object_id) == ()
    retry = idempotency.begin("subject-a", session.object_id, request)
    assert retry.outcome == "STARTED"
    assert retry.turn_id != result.turn_id
    database.dispose()
