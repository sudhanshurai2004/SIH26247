"""Small deterministic Elo-style skill model for abstract training tags."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import pow

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.db.models import Role, SkillRatingRecord, TrainingSessionRecord, User
from core.db.security import AuthorizationError, require_role
from core.scoring import ScoreReport

DEFAULT_RATING = 1_000.0
K_FACTOR = 24.0


@dataclass(frozen=True)
class SkillUpdate:
    """One persisted rating adjustment tied to a scored abstract skill tag."""

    skill_tag: str
    previous_rating: float
    new_rating: float
    outcome: float
    attempts: int


@dataclass(frozen=True)
class ScenarioOption:
    """An available profile candidate for weakness-targeted selection."""

    profile_id: str
    difficulty: int
    skill_tags: tuple[str, ...]


class SkillModel:
    """Persist per-skill ratings while excluding interrupted training attempts."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def update_from_report(
        self,
        *,
        actor_id: str,
        trainee_id: str,
        report: ScoreReport,
        difficulty: int,
    ) -> tuple[SkillUpdate, ...]:
        """Apply node-level outcomes only when the report is rating eligible."""
        if not report.rating_eligible:
            return ()
        with self._session_factory.begin() as db:
            actor = require_role(db.get(User, actor_id), [Role.INSTRUCTOR, Role.ADMIN])
            _require_staff_unit_access(db, actor, trainee_id)
            return _apply_report_in_transaction(
                db,
                trainee_id=trainee_id,
                report=report,
                difficulty=difficulty,
            )

    def apply_session_report_once(
        self,
        *,
        actor_id: str,
        session_id: str,
        report: ScoreReport,
        difficulty: int,
    ) -> tuple[SkillUpdate, ...]:
        """Atomically consume one eligible session for ratings at most once.

        The session flag and all Elo updates share one SQLite transaction, so
        duplicate score requests cannot increment ratings twice.
        """
        if not report.rating_eligible:
            return ()
        with self._session_factory.begin() as db:
            actor = require_role(db.get(User, actor_id), [Role.INSTRUCTOR, Role.ADMIN])
            training_session = db.get(TrainingSessionRecord, session_id)
            if training_session is None:
                raise ValueError("session does not exist")
            _require_staff_unit_access(db, actor, training_session.trainee_id)
            if not training_session.rating_eligible or training_session.rating_applied:
                return ()
            if training_session.score_json is None:
                raise ValueError("session must be scored before applying skill ratings")
            updates = _apply_report_in_transaction(
                db,
                trainee_id=training_session.trainee_id,
                report=report,
                difficulty=difficulty,
            )
            training_session.rating_applied = True
            return updates

    def ratings_for(self, *, actor_id: str, trainee_id: str) -> dict[str, float]:
        """Read ratings for the trainee themselves or instructional staff."""
        with self._session_factory() as db:
            actor = require_role(
                db.get(User, actor_id), [Role.TRAINEE, Role.INSTRUCTOR, Role.ADMIN]
            )
            if actor.role == Role.TRAINEE.value and actor.user_id != trainee_id:
                raise AuthorizationError("trainees may only read their own ratings")
            # An unknown ID has no rating rows. Preserve the dashboard-friendly
            # empty result while still preventing an instructor from probing a
            # known trainee assigned to another local unit.
            if actor.role in {Role.INSTRUCTOR.value, Role.ADMIN.value}:
                if db.get(User, trainee_id) is not None:
                    _require_staff_unit_access(db, actor, trainee_id)
            rows = db.scalars(
                select(SkillRatingRecord)
                .where(SkillRatingRecord.trainee_id == trainee_id)
                .order_by(SkillRatingRecord.skill_tag)
            )
            return {row.skill_tag: float(row.rating) for row in rows}


def _apply_report_in_transaction(
    db: Session,
    *,
    trainee_id: str,
    report: ScoreReport,
    difficulty: int,
) -> tuple[SkillUpdate, ...]:
    """Mutate rating rows using an existing authorized SQLite transaction."""
    trainee = db.get(User, trainee_id)
    if trainee is None or trainee.role != Role.TRAINEE.value:
        raise AuthorizationError("skill ratings require a trainee")
    scenario_rating = _difficulty_rating(difficulty)
    updates: list[SkillUpdate] = []
    for node in report.node_results:
        if node.max_points <= 0:
            continue
        outcome = node.points / node.max_points
        for skill_tag in node.skill_tags:
            record = db.scalar(
                select(SkillRatingRecord).where(
                    SkillRatingRecord.trainee_id == trainee_id,
                    SkillRatingRecord.skill_tag == skill_tag,
                )
            )
            if record is None:
                record = SkillRatingRecord(
                    trainee_id=trainee_id,
                    skill_tag=skill_tag,
                    rating=DEFAULT_RATING,
                    attempts=0,
                )
                db.add(record)
                db.flush()
            expected = _expected_score(record.rating, scenario_rating)
            previous_rating = float(record.rating)
            record.rating = round(previous_rating + K_FACTOR * (outcome - expected), 6)
            record.attempts += 1
            updates.append(
                SkillUpdate(
                    skill_tag=skill_tag,
                    previous_rating=previous_rating,
                    new_rating=float(record.rating),
                    outcome=round(outcome, 6),
                    attempts=record.attempts,
                )
            )
    return tuple(updates)


def select_next_scenario(
    options: Iterable[ScenarioOption],
    ratings: dict[str, float],
) -> ScenarioOption:
    """Choose the option covering the lowest-rated skill, with stable tie breaks."""
    candidates = tuple(options)
    if not candidates:
        raise ValueError("at least one scenario option is required")

    def option_key(option: ScenarioOption) -> tuple[float, int, str]:
        weakest = min(
            (ratings.get(tag, DEFAULT_RATING) for tag in option.skill_tags), default=DEFAULT_RATING
        )
        # Lower weakness is selected first; lower difficulty is a stable tie break.
        return (weakest, option.difficulty, option.profile_id)

    return min(candidates, key=option_key)


def _difficulty_rating(difficulty: int) -> float:
    if not 1 <= difficulty <= 5:
        raise ValueError("difficulty must be between 1 and 5")
    return 800.0 + 100.0 * (difficulty - 1)


def _expected_score(rating: float, scenario_rating: float) -> float:
    return 1.0 / (1.0 + pow(10.0, (scenario_rating - rating) / 400.0))


def _require_staff_unit_access(db: Session, actor: User, trainee_id: str) -> None:
    """Allow admins globally and instructors only inside their persisted unit."""
    if actor.role == Role.ADMIN.value:
        return
    trainee = db.get(User, trainee_id)
    if trainee is None or trainee.role != Role.TRAINEE.value:
        raise AuthorizationError("skill ratings require a trainee")
    if actor.role == Role.INSTRUCTOR.value and actor.unit_id != trainee.unit_id:
        raise AuthorizationError("instructors may only access trainees in their own unit")
