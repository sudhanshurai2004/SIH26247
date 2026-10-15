"""SQLite ORM models for local users, sessions, and idempotent trainee events."""

from __future__ import annotations

from enum import Enum

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all local SQLite tables."""


class Role(str, Enum):
    """Roles allowed by the offline trainer."""

    TRAINEE = "trainee"
    INSTRUCTOR = "instructor"
    ADMIN = "admin"


class SessionStatus(str, Enum):
    """Lifecycle states relevant to replay and adaptive-rating eligibility."""

    ACTIVE = "active"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"


class User(Base):
    """Local user identity; PINs are stored only as salted PBKDF2 hashes."""

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(64), nullable=False, default="local-unit")
    pin_hash: Mapped[str] = mapped_column(String(512), nullable=False)


class TrainingSessionRecord(Base):
    """A local scenario attempt and its optional deterministic score report."""

    __tablename__ = "training_sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trainee_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    scenario_json: Mapped[str] = mapped_column(Text, nullable=False)
    assignment_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    selection_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="fixed")
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    rating_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rating_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    score_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class DoctrineRecord(Base):
    """Validated doctrine YAML stored locally for replayable evaluation."""

    __tablename__ = "doctrines"
    __table_args__ = (UniqueConstraint("doctrine_id", "version", name="uq_doctrine_id_version"),)

    record_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doctrine_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    yaml_text: Mapped[str] = mapped_column(Text, nullable=False)


class SkillRatingRecord(Base):
    """Per-trainee Elo-style state for one abstract skill tag."""

    __tablename__ = "skill_ratings"
    __table_args__ = (UniqueConstraint("trainee_id", "skill_tag", name="uq_skill_trainee_tag"),)

    record_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trainee_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    skill_tag: Mapped[str] = mapped_column(String(32), nullable=False)
    rating: Mapped[float] = mapped_column(nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TraineeEventRecord(Base):
    """One unique client event. event_id is the idempotency key."""

    __tablename__ = "trainee_events"
    __table_args__ = (UniqueConstraint("session_id", "sequence", name="uq_event_session_sequence"),)

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("training_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    t_offset_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    event_json: Mapped[str] = mapped_column(Text, nullable=False)
