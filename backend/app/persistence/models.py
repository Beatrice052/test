"""SQLAlchemy persistence schema for sessions, turns, snapshots, and coordination."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ExternalSubjectRecord(Base):
    __tablename__ = "users_or_external_subjects"

    subject_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)


class SessionRecord(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_id: Mapped[str] = mapped_column(
        ForeignKey("users_or_external_subjects.subject_id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active_context_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    latest_answer_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)

    __table_args__ = (Index("ix_sessions_owner_updated", "subject_id", "updated_at"),)


class TurnRecord(Base):
    __tablename__ = "turns"

    turn_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(256), nullable=False)
    client_turn_id: Mapped[str] = mapped_column(String(128), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    request_json: Mapped[str] = mapped_column(Text, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    decision_json: Mapped[str | None] = mapped_column(Text)
    safe_state_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error_json: Mapped[str | None] = mapped_column(Text)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)

    __table_args__ = (
        Index("ix_turns_owner_id", "subject_id", "turn_id"),
        Index("ix_turns_owner_session", "subject_id", "session_id", "created_at"),
    )


class AnswerSnapshotRecord(Base):
    __tablename__ = "answer_snapshots"

    answer_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False)
    turn_id: Mapped[str] = mapped_column(ForeignKey("turns.turn_id"), nullable=False, unique=True)
    subject_id: Mapped[str] = mapped_column(String(256), nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)

    __table_args__ = (
        Index("ix_answers_owner_id", "subject_id", "answer_id"),
        Index("ix_answers_owner_session", "subject_id", "session_id", "created_at"),
    )


class DatasetArtifactRecord(Base):
    __tablename__ = "dataset_artifacts"

    dataset_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    answer_id: Mapped[str] = mapped_column(ForeignKey("answer_snapshots.answer_id"), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(256), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    relative_path: Mapped[str | None] = mapped_column(String(512))
    payload_json: Mapped[str | None] = mapped_column(Text)
    sensitivity: Mapped[str] = mapped_column(String(32), nullable=False, default="internal")
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)


class EvidenceArtifactRecord(Base):
    __tablename__ = "evidence_artifacts"

    evidence_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    answer_id: Mapped[str] = mapped_column(ForeignKey("answer_snapshots.answer_id"), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(256), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_keys"

    idempotency_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[str] = mapped_column(String(256), nullable=False)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False)
    client_turn_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_turn_id: Mapped[str] = mapped_column(String(128), nullable=False)
    answer_id: Mapped[str | None] = mapped_column(String(128))
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "subject_id", "session_id", "client_turn_id", name="uq_idempotency_owner_turn"
        ),
    )


class SessionLockRecord(Base):
    __tablename__ = "session_locks"

    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(256), nullable=False)
    owner_turn_id: Mapped[str] = mapped_column(String(128), nullable=False)
    lease_until_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    heartbeat_at: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)


class SemanticPackageRefRecord(Base):
    __tablename__ = "semantic_package_refs"

    package_version: Mapped[str] = mapped_column(String(128), primary_key=True)
    manifest_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(512), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)


class FeedbackRecord(Base):
    __tablename__ = "feedback"

    feedback_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(256), nullable=False)
    answer_id: Mapped[str] = mapped_column(ForeignKey("answer_snapshots.answer_id"), nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
