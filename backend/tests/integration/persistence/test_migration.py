"""The checked-in Alembic migration creates the authoritative table set."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.persistence.ids import uuid7


def test_initial_migration_upgrade() -> None:
    database_path = Path(".cache") / f"migration-{uuid7()}.db"
    database_path.parent.mkdir(exist_ok=True)
    try:
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
        command.upgrade(config, "head")

        engine = create_engine(f"sqlite:///{database_path.as_posix()}")
        tables = set(inspect(engine).get_table_names())
        assert {
            "users_or_external_subjects",
            "sessions",
            "turns",
            "answer_snapshots",
            "dataset_artifacts",
            "evidence_artifacts",
            "idempotency_keys",
            "session_locks",
            "semantic_package_refs",
            "feedback",
        }.issubset(tables)
        engine.dispose()
    finally:
        database_path.unlink(missing_ok=True)
