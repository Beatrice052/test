"""Database lifecycle and transactional session factory."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.persistence.models import Base


class Database:
    """Own the SQLAlchemy engine used by all persistence adapters."""

    def __init__(self, url: str) -> None:
        engine_kwargs: dict[str, object] = {}
        if url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        if url in {"sqlite://", "sqlite:///:memory:"}:
            engine_kwargs["poolclass"] = StaticPool
        self.engine = create_engine(url, future=True, **engine_kwargs)
        if url.startswith("sqlite"):
            event.listen(self.engine, "connect", self._enable_sqlite_integrity)
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
        )

    @staticmethod
    def _enable_sqlite_integrity(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    def create_schema(self) -> None:
        """Create the POC schema; production startup uses Alembic upgrade."""

        Base.metadata.create_all(self.engine)

    def schema_ready(self) -> bool:
        required = {"sessions", "turns", "answer_snapshots", "idempotency_keys", "session_locks"}
        return required.issubset(set(inspect(self.engine).get_table_names()))

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()


def ensure_sqlite_parent(database_url: str) -> None:
    """Create only the configured SQLite parent directory, never a user-supplied path."""

    prefix = "sqlite:///"
    if not database_url.startswith(prefix) or database_url.endswith(":memory:"):
        return
    path = Path(database_url.removeprefix(prefix))
    path.parent.mkdir(parents=True, exist_ok=True)


def engine_from_url(database_url: str) -> Engine:
    """Small migration helper."""

    ensure_sqlite_parent(database_url)
    return create_engine(database_url, future=True)
