"""Owned session and turn persistence.

Every lookup includes subject_id in SQL; callers never receive an unowned row to check later.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, select

from app.contracts.analysis import TurnDecision
from app.contracts.common import Provenance, semantic_hash
from app.contracts.request import ChatRequest
from app.contracts.session import ActiveAnalyticalContext, SessionContext
from app.persistence.database import Database
from app.persistence.errors import (
    OwnedObjectNotFound,
    SessionArchived,
    TurnCancelled,
    VersionConflict,
)
from app.persistence.ids import new_id
from app.persistence.models import (
    ExternalSubjectRecord,
    IdempotencyRecord,
    SessionRecord,
    TurnRecord,
)
from app.persistence.serialization import dump_json, dump_time, load_json, load_time, utc_now

RECOVERABLE_TURN_STATES = ("PENDING", "RUNNING", "FAILED")
SAFE_STATE_KEYS = frozenset(
    {
        "node",
        "terminal_status",
        "semantic_package_version",
        "candidate_ids",
        "analysis_plan_id",
        "analysis_plan_hash",
        "answer_id",
        "error_codes",
    }
)


class SessionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _owned_session_query(subject_id: str, session_id: str) -> Select[tuple[SessionRecord]]:
        return select(SessionRecord).where(
            SessionRecord.subject_id == subject_id,
            SessionRecord.session_id == session_id,
        )

    def create_session(self, subject_id: str, *, title: str = "新分析") -> SessionContext:
        now = utc_now()
        session_id = new_id("ses")
        active_context = ActiveAnalyticalContext()
        with self.database.session() as db:
            subject = db.get(ExternalSubjectRecord, subject_id)
            if subject is None:
                db.add(ExternalSubjectRecord(subject_id=subject_id, created_at=dump_time(now)))
            record = SessionRecord(
                session_id=session_id,
                subject_id=subject_id,
                title=title[:256],
                version=0,
                archived=False,
                active_context_json=dump_json(active_context),
                latest_answer_id=None,
                created_at=dump_time(now),
                updated_at=dump_time(now),
            )
            db.add(record)
        return self._to_context(record)

    def get_session(self, subject_id: str, session_id: str) -> SessionContext:
        with self.database.session() as db:
            record = db.scalar(self._owned_session_query(subject_id, session_id))
            if record is None:
                raise OwnedObjectNotFound("session not found")
            return self._to_context(record)

    def list_sessions(
        self, subject_id: str, *, include_archived: bool = False, limit: int = 50
    ) -> tuple[SessionContext, ...]:
        statement = select(SessionRecord).where(SessionRecord.subject_id == subject_id)
        if not include_archived:
            statement = statement.where(SessionRecord.archived.is_(False))
        statement = statement.order_by(SessionRecord.updated_at.desc()).limit(limit)
        with self.database.session() as db:
            return tuple(self._to_context(record) for record in db.scalars(statement))

    def update_title(
        self, subject_id: str, session_id: str, *, title: str, expected_version: int
    ) -> SessionContext:
        with self.database.session() as db:
            record = db.scalar(self._owned_session_query(subject_id, session_id))
            if record is None:
                raise OwnedObjectNotFound("session not found")
            if record.version != expected_version:
                raise VersionConflict("session version does not match")
            record.title = title[:256]
            record.version += 1
            record.updated_at = dump_time(utc_now())
            db.flush()
            return self._to_context(record)

    def archive_session(self, subject_id: str, session_id: str) -> SessionContext:
        with self.database.session() as db:
            record = db.scalar(self._owned_session_query(subject_id, session_id))
            if record is None:
                raise OwnedObjectNotFound("session not found")
            record.archived = True
            record.version += 1
            record.updated_at = dump_time(utc_now())
            db.flush()
            return self._to_context(record)

    def assert_writable(self, subject_id: str, session_id: str) -> None:
        context = self.get_session(subject_id, session_id)
        if context.archived:
            raise SessionArchived("archived session is read-only")

    def get_turn(self, subject_id: str, turn_id: str) -> TurnRecord:
        with self.database.session() as db:
            record = db.scalar(
                select(TurnRecord).where(
                    TurnRecord.subject_id == subject_id,
                    TurnRecord.turn_id == turn_id,
                )
            )
            if record is None:
                raise OwnedObjectNotFound("turn not found")
            db.expunge(record)
            return record

    def list_turns(
        self, subject_id: str, session_id: str, *, limit: int = 100
    ) -> tuple[TurnRecord, ...]:
        with self.database.session() as db:
            records = tuple(
                db.scalars(
                    select(TurnRecord)
                    .where(
                        TurnRecord.subject_id == subject_id,
                        TurnRecord.session_id == session_id,
                    )
                    .order_by(TurnRecord.created_at)
                    .limit(limit)
                )
            )
            for record in records:
                db.expunge(record)
            return records

    def cancel_turn(self, subject_id: str, turn_id: str) -> TurnRecord:
        with self.database.session() as db:
            record = db.scalar(
                select(TurnRecord).where(
                    TurnRecord.subject_id == subject_id,
                    TurnRecord.turn_id == turn_id,
                )
            )
            if record is None:
                raise OwnedObjectNotFound("turn not found")
            if record.status not in {"PENDING", "RUNNING"}:
                raise ValueError(f"turn cannot be cancelled from {record.status}")
            record.status = "CANCELLED"
            record.retryable = False
            record.error_json = dump_json({"code": "SESSION_CANCELLED"})
            record.updated_at = dump_time(utc_now())
            idempotency = db.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.subject_id == subject_id,
                    IdempotencyRecord.current_turn_id == turn_id,
                )
            )
            if idempotency is not None:
                idempotency.state = "FAILED"
                idempotency.retryable = False
                idempotency.updated_at = record.updated_at
            db.flush()
            db.expunge(record)
            return record

    def mark_turn_cancelled(self, subject_id: str, turn_id: str) -> None:
        """Idempotently stop a running turn and its idempotency claim."""

        with self.database.session() as db:
            record = db.scalar(
                select(TurnRecord).where(
                    TurnRecord.subject_id == subject_id,
                    TurnRecord.turn_id == turn_id,
                )
            )
            if record is None:
                raise OwnedObjectNotFound("turn not found")
            if record.status == "COMPLETED":
                return
            record.status = "CANCELLED"
            record.retryable = False
            record.error_json = dump_json({"code": "SESSION_CANCELLED"})
            record.updated_at = dump_time(utc_now())
            idempotency = db.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.subject_id == subject_id,
                    IdempotencyRecord.current_turn_id == turn_id,
                )
            )
            if idempotency is not None:
                idempotency.state = "FAILED"
                idempotency.retryable = False
                idempotency.updated_at = record.updated_at

    def save_turn_decision(self, subject_id: str, turn_id: str, decision: TurnDecision) -> None:
        with self.database.session() as db:
            record = db.scalar(
                select(TurnRecord).where(
                    TurnRecord.subject_id == subject_id,
                    TurnRecord.turn_id == turn_id,
                )
            )
            if record is None:
                raise OwnedObjectNotFound("turn not found")
            record.decision_json = dump_json(decision)
            record.updated_at = dump_time(utc_now())

    def save_safe_state(self, subject_id: str, turn_id: str, state: dict[str, Any]) -> None:
        unexpected = set(state) - SAFE_STATE_KEYS
        if unexpected:
            raise ValueError(f"unsafe checkpoint fields: {sorted(unexpected)}")
        with self.database.session() as db:
            record = db.scalar(
                select(TurnRecord).where(
                    TurnRecord.subject_id == subject_id,
                    TurnRecord.turn_id == turn_id,
                )
            )
            if record is None:
                raise OwnedObjectNotFound("turn not found")
            if record.status == "CANCELLED":
                raise TurnCancelled("cancelled turn cannot advance checkpoint state")
            record.safe_state_json = dump_json(state)
            record.updated_at = dump_time(utc_now())

    def mark_turn_failed(
        self,
        subject_id: str,
        turn_id: str,
        *,
        error: dict[str, Any],
        retryable: bool,
    ) -> None:
        with self.database.session() as db:
            record = db.scalar(
                select(TurnRecord).where(
                    TurnRecord.subject_id == subject_id,
                    TurnRecord.turn_id == turn_id,
                )
            )
            if record is None:
                raise OwnedObjectNotFound("turn not found")
            if record.status == "CANCELLED":
                return
            record.status = "FAILED"
            record.error_json = dump_json(error)
            record.retryable = retryable
            record.updated_at = dump_time(utc_now())

    def recoverable_turns(self, subject_id: str) -> tuple[TurnRecord, ...]:
        with self.database.session() as db:
            records = tuple(
                db.scalars(
                    select(TurnRecord)
                    .where(
                        TurnRecord.subject_id == subject_id,
                        TurnRecord.status.in_(RECOVERABLE_TURN_STATES),
                    )
                    .order_by(TurnRecord.created_at)
                )
            )
            for record in records:
                db.expunge(record)
            return records

    @staticmethod
    def request_from_turn(record: TurnRecord) -> ChatRequest:
        return ChatRequest.model_validate_json(record.request_json)

    @staticmethod
    def safe_state_from_turn(record: TurnRecord) -> dict[str, Any]:
        value = load_json(record.safe_state_json)
        if not isinstance(value, dict):
            raise ValueError("turn safe state is not an object")
        return value

    @staticmethod
    def _to_context(record: SessionRecord) -> SessionContext:
        active_context = ActiveAnalyticalContext.model_validate_json(record.active_context_json)
        created_at = load_time(record.created_at)
        payload = {
            "session_id": record.session_id,
            "subject_id": record.subject_id,
            "title": record.title,
            "version": record.version,
            "archived": record.archived,
            "active_context": active_context,
            "latest_answer_id": record.latest_answer_id,
        }
        return SessionContext(
            object_id=record.session_id,
            created_at=created_at,
            content_hash=semantic_hash(payload),
            provenance=Provenance(producer="persistence.session_repository"),
            subject_id=record.subject_id,
            title=record.title,
            version=record.version,
            archived=record.archived,
            active_context=active_context,
            latest_answer_id=record.latest_answer_id,
            updated_at=load_time(record.updated_at),
        )
