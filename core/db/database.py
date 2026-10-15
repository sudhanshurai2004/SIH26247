"""Local SQLite engine and session-factory helpers."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from core.db.models import Base


def create_sqlite_engine(database_path: str | Path) -> Engine:
    """Create a SQLite engine with foreign-key enforcement enabled."""
    path = str(database_path)
    if path == ":memory:":
        url = "sqlite+pysqlite:///:memory:"
    else:
        resolved_path = Path(path)
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite+pysqlite:///{resolved_path}"

    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[union-attr]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a unit-of-work factory with objects available after commit."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def initialize_database(engine: Engine) -> None:
    """Create local tables and apply the small additive SQLite compatibility migration."""
    Base.metadata.create_all(engine)
    existing_session_columns = {
        column["name"] for column in inspect(engine).get_columns("training_sessions")
    }
    existing_user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    with engine.begin() as connection:
        # These migrations are fixed source statements, not interpolated user queries.
        if "unit_id" not in existing_user_columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN unit_id TEXT NOT NULL DEFAULT 'local-unit'")
            )
        if "selection_mode" not in existing_session_columns:
            connection.execute(
                text(
                    "ALTER TABLE training_sessions ADD COLUMN selection_mode "
                    "TEXT NOT NULL DEFAULT 'fixed'"
                )
            )
        if "assignment_sequence" not in existing_session_columns:
            connection.execute(
                text(
                    "ALTER TABLE training_sessions ADD COLUMN assignment_sequence "
                    "INTEGER NOT NULL DEFAULT 0"
                )
            )
            # SQLite rowid preserves local insertion order for pre-existing
            # records. New assignments receive an explicit monotonic sequence.
            connection.execute(
                text(
                    "UPDATE training_sessions SET assignment_sequence = rowid "
                    "WHERE assignment_sequence = 0"
                )
            )
        if "rating_applied" not in existing_session_columns:
            connection.execute(
                text(
                    "ALTER TABLE training_sessions ADD COLUMN rating_applied "
                    "BOOLEAN NOT NULL DEFAULT 0"
                )
            )
