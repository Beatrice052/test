"""Lease-based exclusive session lock."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult

from app.persistence.database import Database
from app.persistence.errors import OwnedObjectNotFound, SessionLockConflict
from app.persistence.models import SessionLockRecord, SessionRecord
from app.persistence.serialization import dump_time, utc_now


def _epoch_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


class SessionLockRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def acquire(
        self,
        subject_id: str,
        session_id: str,
        owner_turn_id: str,
        *,
        lease_seconds: int = 120,
    ) -> None:
        now = utc_now()
        with self.database.session() as db:
            owned_session = db.scalar(
                select(SessionRecord.session_id).where(
                    SessionRecord.subject_id == subject_id,
                    SessionRecord.session_id == session_id,
                )
            )
            if owned_session is None:
                raise OwnedObjectNotFound("session not found")
            lock = db.scalar(
                select(SessionLockRecord).where(
                    SessionLockRecord.subject_id == subject_id,
                    SessionLockRecord.session_id == session_id,
                )
            )
            if lock is not None and lock.lease_until_ms > _epoch_ms(now):
                if lock.owner_turn_id == owner_turn_id:
                    self._extend(lock, now, lease_seconds)
                    return
                raise SessionLockConflict("session has another running semantic turn")
            if lock is not None:
                db.delete(lock)
                db.flush()
            db.add(
                SessionLockRecord(
                    session_id=session_id,
                    subject_id=subject_id,
                    owner_turn_id=owner_turn_id,
                    lease_until_ms=_epoch_ms(now + timedelta(seconds=lease_seconds)),
                    heartbeat_at=dump_time(now),
                    created_at=dump_time(now),
                )
            )

    def heartbeat(
        self,
        subject_id: str,
        session_id: str,
        owner_turn_id: str,
        *,
        lease_seconds: int = 120,
    ) -> None:
        now = utc_now()
        with self.database.session() as db:
            lock = db.scalar(
                select(SessionLockRecord).where(
                    SessionLockRecord.subject_id == subject_id,
                    SessionLockRecord.session_id == session_id,
                    SessionLockRecord.owner_turn_id == owner_turn_id,
                )
            )
            if lock is None or lock.lease_until_ms <= _epoch_ms(now):
                raise SessionLockConflict("session lock is missing or expired")
            self._extend(lock, now, lease_seconds)

    def release(self, subject_id: str, session_id: str, owner_turn_id: str) -> bool:
        with self.database.session() as db:
            result = cast(
                CursorResult[Any],
                db.execute(
                    delete(SessionLockRecord).where(
                        SessionLockRecord.subject_id == subject_id,
                        SessionLockRecord.session_id == session_id,
                        SessionLockRecord.owner_turn_id == owner_turn_id,
                    )
                ),
            )
            return bool(result.rowcount)

    def release_expired(self, *, now: datetime | None = None) -> int:
        resolved_now = now or utc_now()
        with self.database.session() as db:
            result = cast(
                CursorResult[Any],
                db.execute(
                    delete(SessionLockRecord).where(
                        SessionLockRecord.lease_until_ms <= _epoch_ms(resolved_now)
                    )
                ),
            )
            return int(result.rowcount or 0)

    @staticmethod
    def _extend(lock: SessionLockRecord, now: datetime, lease_seconds: int) -> None:
        lock.lease_until_ms = _epoch_ms(now + timedelta(seconds=lease_seconds))
        lock.heartbeat_at = dump_time(now)
