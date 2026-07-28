from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.sessions.models import (
    ChatMessage,
    MessageKind,
    MessageRole,
    PendingClarification,
)
from app.sessions.store import InMemorySessionStore


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 7, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


def _store(clock: MutableClock, *, capacity: int = 2) -> InMemorySessionStore:
    return InMemorySessionStore(
        ttl_seconds=10,
        capacity=capacity,
        max_messages=3,
        clock=clock,
    )


def test_session_store_preserves_pending_clarification_and_can_reset() -> None:
    clock = MutableClock()
    store = _store(clock)
    session = store.create("session-001")
    store.append_message(
        session.session_id,
        ChatMessage(
            message_id="m-001",
            role=MessageRole.USER,
            kind=MessageKind.QUESTION,
            content="看看最近的失败情况。",
        ),
    )
    pending = PendingClarification(
        clarification_id="c-001",
        question="按Channel、Route还是日期趋势？",
        missing_slot="breakdown_dimension",
        allowed_choices=["channel", "route", "date_trend"],
        partial_analysis_plan={"metric_concepts": ["failure_rate"]},
        original_user_question="看看最近的失败情况。",
    )

    updated = store.set_pending(session.session_id, pending)

    assert updated.pending_clarification == pending
    assert updated.messages[0].content == "看看最近的失败情况。"
    reset = store.reset(session.session_id)
    assert reset.messages == []
    assert reset.pending_clarification is None


def test_session_store_is_bounded_lru() -> None:
    clock = MutableClock()
    store = _store(clock, capacity=2)
    store.create("session-001")
    clock.advance(1)
    store.create("session-002")
    store.get("session-001")
    clock.advance(1)
    store.create("session-003")

    assert store.get("session-002") is None
    assert store.get("session-001") is not None
    assert store.get("session-003") is not None


def test_session_store_expires_at_ttl() -> None:
    clock = MutableClock()
    store = _store(clock)
    store.create("session-001")

    clock.advance(10)

    assert store.get("session-001") is None
    assert store.size == 0


def test_session_store_limits_message_history() -> None:
    clock = MutableClock()
    store = _store(clock)
    store.create("session-001")
    for index in range(5):
        store.append_message(
            "session-001",
            ChatMessage(
                message_id=f"m-{index}",
                role=MessageRole.USER,
                kind=MessageKind.QUESTION,
                content=str(index),
            ),
        )

    state = store.get("session-001")

    assert state is not None
    assert [message.content for message in state.messages] == ["2", "3", "4"]


def test_store_returns_copies_not_mutable_internal_state() -> None:
    clock = MutableClock()
    store = _store(clock)
    returned = store.create("session-001")
    returned.messages.append(
        ChatMessage(
            message_id="external",
            role=MessageRole.USER,
            kind=MessageKind.QUESTION,
            content="should not leak",
        )
    )

    stored = store.get("session-001")

    assert stored is not None
    assert stored.messages == []
