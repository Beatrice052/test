from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from datetime import datetime, timedelta
from threading import RLock
from uuid import uuid4

from app.sessions.models import ChatMessage, PendingClarification, SessionState, utc_now


class InMemorySessionStore:
    """Thread-safe bounded LRU store for the single-process POC.

    Copies are returned at the boundary so callers cannot mutate stored state
    without an explicit store operation.
    """

    def __init__(
        self,
        *,
        ttl_seconds: int,
        capacity: int,
        max_messages: int,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if ttl_seconds <= 0 or capacity <= 0 or max_messages <= 1:
            raise ValueError("session limits must be positive")
        self._ttl = timedelta(seconds=ttl_seconds)
        self._capacity = capacity
        self._max_messages = max_messages
        self._clock = clock
        self._items: OrderedDict[str, SessionState] = OrderedDict()
        self._lock = RLock()

    @property
    def size(self) -> int:
        with self._lock:
            self._purge_expired_locked(self._clock())
            return len(self._items)

    def create(self, session_id: str | None = None) -> SessionState:
        now = self._clock()
        identifier = session_id or f"session-{uuid4()}"
        with self._lock:
            self._purge_expired_locked(now)
            existing = self._items.get(identifier)
            if existing is not None:
                return self._copy(self._touch_locked(identifier, existing, now))
            state = SessionState(session_id=identifier, created_at=now, updated_at=now)
            self._items[identifier] = state
            self._items.move_to_end(identifier)
            self._evict_over_capacity_locked()
            return self._copy(state)

    def get(self, session_id: str) -> SessionState | None:
        now = self._clock()
        with self._lock:
            self._purge_expired_locked(now)
            state = self._items.get(session_id)
            if state is None:
                return None
            return self._copy(self._touch_locked(session_id, state, now))

    def get_or_create(self, session_id: str | None) -> SessionState:
        if session_id:
            state = self.get(session_id)
            if state is not None:
                return state
        return self.create(session_id)

    def append_message(self, session_id: str, message: ChatMessage) -> SessionState:
        now = self._clock()
        with self._lock:
            self._purge_expired_locked(now)
            state = self._require_locked(session_id)
            messages = [*state.messages, message][-self._max_messages :]
            updated = state.model_copy(update={"messages": messages, "updated_at": now}, deep=True)
            self._items[session_id] = updated
            self._items.move_to_end(session_id)
            return self._copy(updated)

    def set_pending(self, session_id: str, pending: PendingClarification | None) -> SessionState:
        now = self._clock()
        with self._lock:
            self._purge_expired_locked(now)
            state = self._require_locked(session_id)
            updated = state.model_copy(
                update={"pending_clarification": pending, "updated_at": now}, deep=True
            )
            self._items[session_id] = updated
            self._items.move_to_end(session_id)
            return self._copy(updated)

    def save(self, state: SessionState) -> SessionState:
        now = self._clock()
        with self._lock:
            self._purge_expired_locked(now)
            if state.session_id not in self._items:
                raise KeyError(f"unknown session: {state.session_id}")
            updated = state.model_copy(update={"updated_at": now}, deep=True)
            updated.messages = updated.messages[-self._max_messages :]
            self._items[state.session_id] = updated
            self._items.move_to_end(state.session_id)
            return self._copy(updated)

    def reset(self, session_id: str) -> SessionState:
        now = self._clock()
        with self._lock:
            self._purge_expired_locked(now)
            fresh = SessionState(session_id=session_id, created_at=now, updated_at=now)
            self._items[session_id] = fresh
            self._items.move_to_end(session_id)
            self._evict_over_capacity_locked()
            return self._copy(fresh)

    def _require_locked(self, session_id: str) -> SessionState:
        state = self._items.get(session_id)
        if state is None:
            raise KeyError(f"unknown session: {session_id}")
        return state

    def _touch_locked(self, session_id: str, state: SessionState, now: datetime) -> SessionState:
        touched = state.model_copy(update={"updated_at": now}, deep=True)
        self._items[session_id] = touched
        self._items.move_to_end(session_id)
        return touched

    def _purge_expired_locked(self, now: datetime) -> None:
        expired = [key for key, value in self._items.items() if now - value.updated_at >= self._ttl]
        for key in expired:
            self._items.pop(key, None)

    def _evict_over_capacity_locked(self) -> None:
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)

    @staticmethod
    def _copy(state: SessionState) -> SessionState:
        return state.model_copy(deep=True)
