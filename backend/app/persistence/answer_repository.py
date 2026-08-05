"""Immutable answer snapshots and atomic turn/idempotency completion."""

from __future__ import annotations

from sqlalchemy import select

from app.contracts.dataset import TabularDataset
from app.contracts.evidence import EvidenceArtifactRef
from app.contracts.session import ActiveAnalyticalContext, AnswerSnapshot
from app.persistence.database import Database
from app.persistence.errors import OwnedObjectNotFound, PersistenceError, TurnCancelled
from app.persistence.models import (
    AnswerSnapshotRecord,
    IdempotencyRecord,
    SessionRecord,
    TurnRecord,
)
from app.persistence.serialization import dump_json, dump_time, utc_now


class AnswerRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def persist_answer(
        self,
        subject_id: str,
        turn_id: str,
        snapshot: AnswerSnapshot,
        active_context: ActiveAnalyticalContext,
    ) -> None:
        """Atomically persist answer, complete the turn/key, and advance session context."""

        now = utc_now()
        with self.database.session() as db:
            turn = db.scalar(
                select(TurnRecord).where(
                    TurnRecord.subject_id == subject_id,
                    TurnRecord.turn_id == turn_id,
                )
            )
            if turn is None or turn.session_id != snapshot.session_id:
                raise OwnedObjectNotFound("turn not found")
            if turn.status == "CANCELLED":
                raise TurnCancelled("cancelled turn cannot publish an answer")
            if turn.status != "RUNNING":
                raise PersistenceError(f"turn cannot publish an answer from {turn.status}")
            session = db.scalar(
                select(SessionRecord).where(
                    SessionRecord.subject_id == subject_id,
                    SessionRecord.session_id == turn.session_id,
                )
            )
            if session is None:
                raise OwnedObjectNotFound("session not found")
            idempotency = db.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.subject_id == subject_id,
                    IdempotencyRecord.session_id == turn.session_id,
                    IdempotencyRecord.client_turn_id == turn.client_turn_id,
                    IdempotencyRecord.current_turn_id == turn_id,
                )
            )
            if idempotency is None:
                raise OwnedObjectNotFound("idempotency key not found")

            db.add(
                AnswerSnapshotRecord(
                    answer_id=snapshot.object_id,
                    session_id=snapshot.session_id,
                    turn_id=turn_id,
                    subject_id=subject_id,
                    snapshot_json=dump_json(snapshot),
                    content_hash=snapshot.content_hash,
                    created_at=dump_time(snapshot.created_at),
                )
            )
            turn.status = "COMPLETED"
            turn.retryable = False
            turn.updated_at = dump_time(now)
            idempotency.state = "COMPLETED"
            idempotency.retryable = False
            idempotency.answer_id = snapshot.object_id
            idempotency.updated_at = dump_time(now)
            session.latest_answer_id = snapshot.object_id
            session.active_context_json = dump_json(active_context)
            session.version += 1
            session.updated_at = dump_time(now)

    def get_answer(self, subject_id: str, answer_id: str) -> AnswerSnapshot:
        with self.database.session() as db:
            record = db.scalar(
                select(AnswerSnapshotRecord).where(
                    AnswerSnapshotRecord.subject_id == subject_id,
                    AnswerSnapshotRecord.answer_id == answer_id,
                )
            )
            if record is None:
                raise OwnedObjectNotFound("answer not found")
            return AnswerSnapshot.model_validate_json(record.snapshot_json)

    def latest_answer(self, subject_id: str, session_id: str) -> AnswerSnapshot | None:
        with self.database.session() as db:
            record = db.scalar(
                select(AnswerSnapshotRecord)
                .where(
                    AnswerSnapshotRecord.subject_id == subject_id,
                    AnswerSnapshotRecord.session_id == session_id,
                )
                .order_by(AnswerSnapshotRecord.created_at.desc())
                .limit(1)
            )
            return (
                None if record is None else AnswerSnapshot.model_validate_json(record.snapshot_json)
            )

    def list_answers(
        self, subject_id: str, session_id: str, *, limit: int = 100
    ) -> tuple[AnswerSnapshot, ...]:
        with self.database.session() as db:
            records = tuple(
                db.scalars(
                    select(AnswerSnapshotRecord)
                    .where(
                        AnswerSnapshotRecord.subject_id == subject_id,
                        AnswerSnapshotRecord.session_id == session_id,
                    )
                    .order_by(AnswerSnapshotRecord.created_at)
                    .limit(limit)
                )
            )
            return tuple(
                AnswerSnapshot.model_validate_json(record.snapshot_json) for record in records
            )

    def get_dataset(self, subject_id: str, dataset_id: str) -> TabularDataset:
        """Resolve a dataset only inside snapshots owned by the requesting subject."""

        with self.database.session() as db:
            records = tuple(
                db.scalars(
                    select(AnswerSnapshotRecord)
                    .where(AnswerSnapshotRecord.subject_id == subject_id)
                    .order_by(AnswerSnapshotRecord.created_at.desc())
                )
            )
            for record in records:
                snapshot = AnswerSnapshot.model_validate_json(record.snapshot_json)
                if snapshot.dataset_bundle is None:
                    continue
                match = next(
                    (
                        item
                        for item in snapshot.dataset_bundle.datasets
                        if item.object_id == dataset_id
                    ),
                    None,
                )
                if match is not None:
                    return match
        raise OwnedObjectNotFound("dataset not found")

    def get_artifact_reference(
        self, subject_id: str, answer_id: str, artifact_id: str
    ) -> EvidenceArtifactRef:
        """Resolve an artifact only through an AnswerSnapshot owned by the subject."""

        answer = self.get_answer(subject_id, answer_id)
        evidence = answer.evidence_package
        if evidence is not None:
            match = next(
                (item for item in evidence.advanced.artifacts if item.artifact_id == artifact_id),
                None,
            )
            if match is not None:
                return match
        raise OwnedObjectNotFound("evidence artifact not found")
