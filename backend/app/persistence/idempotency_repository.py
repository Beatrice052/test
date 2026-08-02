"""Atomic client_turn_id claim and replay handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select

from app.contracts.common import semantic_hash
from app.contracts.request import ChatRequest
from app.persistence.database import Database
from app.persistence.errors import IdempotencyConflict, OwnedObjectNotFound, SessionArchived
from app.persistence.ids import new_id
from app.persistence.models import IdempotencyRecord, SessionRecord, TurnRecord
from app.persistence.serialization import dump_json, dump_time, utc_now

type ClaimOutcome = Literal["STARTED", "COMPLETED", "RUNNING", "FAILED"]


@dataclass(frozen=True, slots=True)
class IdempotencyClaim:
    outcome: ClaimOutcome
    turn_id: str
    attempt: int
    answer_id: str | None = None


class IdempotencyRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def begin(self, subject_id: str, session_id: str, request: ChatRequest) -> IdempotencyClaim:
        payload_hash = semantic_hash(request)
        now = utc_now()
        with self.database.session() as db:
            session_record = db.scalar(
                select(SessionRecord).where(
                    SessionRecord.subject_id == subject_id,
                    SessionRecord.session_id == session_id,
                )
            )
            if session_record is None:
                raise OwnedObjectNotFound("session not found")
            if session_record.archived:
                raise SessionArchived("archived session is read-only")

            record = db.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.subject_id == subject_id,
                    IdempotencyRecord.session_id == session_id,
                    IdempotencyRecord.client_turn_id == request.client_turn_id,
                )
            )
            if record is not None:
                if record.payload_hash != payload_hash:
                    raise IdempotencyConflict("client_turn_id was used with a different payload")
                if record.state == "COMPLETED":
                    return IdempotencyClaim(
                        outcome="COMPLETED",
                        turn_id=record.current_turn_id,
                        attempt=record.attempt,
                        answer_id=record.answer_id,
                    )
                if record.state == "RUNNING":
                    return IdempotencyClaim(
                        outcome="RUNNING",
                        turn_id=record.current_turn_id,
                        attempt=record.attempt,
                    )
                if record.state == "FAILED" and not record.retryable:
                    return IdempotencyClaim(
                        outcome="FAILED",
                        turn_id=record.current_turn_id,
                        attempt=record.attempt,
                    )
                record.attempt += 1
                record.state = "RUNNING"
                record.retryable = False
                record.answer_id = None
                record.current_turn_id = new_id("trn")
                record.updated_at = dump_time(now)
                turn_id = record.current_turn_id
                attempt = record.attempt
            else:
                turn_id = new_id("trn")
                attempt = 1
                db.add(
                    IdempotencyRecord(
                        subject_id=subject_id,
                        session_id=session_id,
                        client_turn_id=request.client_turn_id,
                        payload_hash=payload_hash,
                        state="RUNNING",
                        attempt=attempt,
                        current_turn_id=turn_id,
                        answer_id=None,
                        retryable=False,
                        created_at=dump_time(now),
                        updated_at=dump_time(now),
                    )
                )

            db.add(
                TurnRecord(
                    turn_id=turn_id,
                    session_id=session_id,
                    subject_id=subject_id,
                    client_turn_id=request.client_turn_id,
                    attempt=attempt,
                    status="RUNNING",
                    request_json=dump_json(request),
                    payload_hash=payload_hash,
                    decision_json=None,
                    safe_state_json="{}",
                    error_json=None,
                    retryable=False,
                    created_at=dump_time(now),
                    updated_at=dump_time(now),
                )
            )
            return IdempotencyClaim(outcome="STARTED", turn_id=turn_id, attempt=attempt)

    def mark_failed(self, subject_id: str, turn_id: str, *, retryable: bool) -> None:
        with self.database.session() as db:
            turn = db.scalar(
                select(TurnRecord).where(
                    TurnRecord.subject_id == subject_id,
                    TurnRecord.turn_id == turn_id,
                )
            )
            if turn is None:
                raise OwnedObjectNotFound("turn not found")
            record = db.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.subject_id == subject_id,
                    IdempotencyRecord.session_id == turn.session_id,
                    IdempotencyRecord.client_turn_id == turn.client_turn_id,
                    IdempotencyRecord.current_turn_id == turn_id,
                )
            )
            if record is None:
                raise OwnedObjectNotFound("idempotency key not found")
            record.state = "FAILED"
            record.retryable = retryable
            record.updated_at = dump_time(utc_now())
