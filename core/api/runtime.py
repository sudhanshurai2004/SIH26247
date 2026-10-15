"""Local-only service wiring for FastAPI and desktop development."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from core.adaptive import SkillModel
from core.db import create_session_factory, create_sqlite_engine, initialize_database
from core.scoring import DoctrineRepository
from core.sessions import SessionManager


@dataclass(frozen=True)
class LocalServices:
    """The locally persisted service graph; it never configures remote clients."""

    database_path: Path
    session_factory: sessionmaker[Session]
    sessions: SessionManager
    doctrines: DoctrineRepository
    skills: SkillModel


def create_local_services(database_path: Path | None = None) -> LocalServices:
    """Create and initialize the local SQLite-backed service graph."""
    path = database_path or _database_path_from_environment()
    engine = create_sqlite_engine(path)
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    return LocalServices(
        database_path=path,
        session_factory=session_factory,
        sessions=SessionManager(session_factory),
        doctrines=DoctrineRepository(session_factory),
        skills=SkillModel(session_factory),
    )


def _database_path_from_environment() -> Path:
    configured = os.environ.get("SIH26247_DB_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "data" / "trainer.sqlite3"
