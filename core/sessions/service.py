"""Local session lifecycle and idempotent event ingestion."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from core.contracts import ContractValidationError, validate_versioned_payload
from core.db.models import Role, SessionStatus, TraineeEventRecord, TrainingSessionRecord, User
from core.db.security import AuthorizationError, hash_pin, require_role, verify_pin
from core.generator import (
    DEFAULT_SEMANTIC_NOVELTY_POLICY,
    GENERATOR_V1_VERSION,
    ScenarioValidationError,
    most_similar_recent_scenario,
    scenario_fingerprint,
    validate_playback_scenario,
)
from core.scoring import ScoreReport, load_doctrine, score_scenario, validate_doctrine
from core.serialization import canonical_json

USER_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,63}$")
UNIT_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,63}$")


class SessionManagerError(ValueError):
    """Raised for invalid local session state or event ownership."""


class EventConflictError(SessionManagerError):
    """Raised when an idempotency key is reused with a different event payload."""


@dataclass(frozen=True)
class EventIngestResult:
    """Result of one event-ingestion attempt."""

    event_id: str
    created: bool
    session_status: str
    rating_eligible: bool


@dataclass(frozen=True)
class SessionSnapshot:
    """Read model used by future API/dashboard layers."""

    session_id: str
    scenario: dict[str, Any]
    trainee_id: str
    selection_mode: str
    status: str
    rating_eligible: bool
    rating_applied: bool
    events: tuple[dict[str, Any], ...]
    score: dict[str, Any] | None


@dataclass(frozen=True)
class SessionSummary:
    """Small session-list record that omits trajectory and event payloads."""

    session_id: str
    scenario_id: str
    trainee_id: str
    selection_mode: str
    status: str
    rating_eligible: bool
    total_score: float | None


class SessionManager:
    """Own local session data through ORM queries and explicit role checks."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_bootstrap_admin(self, user_id: str, pin: str, unit_id: str = "local-unit") -> None:
        """Create the first admin only when the local user table is empty."""
        _validate_user_id(user_id)
        _validate_unit_id(unit_id)
        with self._session_factory.begin() as db:
            has_users = db.scalar(select(User.user_id).limit(1)) is not None
            if has_users:
                raise SessionManagerError(
                    "bootstrap admin may only be created in an empty database"
                )
            db.add(
                User(
                    user_id=user_id,
                    role=Role.ADMIN.value,
                    unit_id=unit_id,
                    pin_hash=hash_pin(pin),
                )
            )

    def create_user(
        self,
        *,
        actor_id: str,
        user_id: str,
        role: Role,
        pin: str,
        unit_id: str = "local-unit",
    ) -> None:
        """Create a local user; only an admin may create identities."""
        _validate_user_id(user_id)
        _validate_unit_id(unit_id)
        with self._session_factory.begin() as db:
            require_role(db.get(User, actor_id), [Role.ADMIN])
            if db.get(User, user_id) is not None:
                raise SessionManagerError("user_id already exists")
            db.add(User(user_id=user_id, role=role.value, unit_id=unit_id, pin_hash=hash_pin(pin)))

    def authenticate_pin(self, user_id: str, pin: str) -> bool:
        """Verify a local PIN without exposing the stored hash."""
        with self._session_factory() as db:
            user = db.get(User, user_id)
            return user is not None and verify_pin(pin, user.pin_hash)

    def create_training_session(
        self,
        *,
        actor_id: str,
        session_id: str,
        trainee_id: str,
        scenario: Mapping[str, Any],
        selection_mode: str = "fixed",
    ) -> None:
        """Persist one generated V0 scenario for a trainee.

        Instructor and admin roles can assign a scenario. The scenario is
        validated before persistence so playback never reads an invalid record.
        """
        _validate_session_id(session_id)
        if selection_mode not in {"fixed", "adaptive"}:
            raise SessionManagerError("selection_mode must be 'fixed' or 'adaptive'")
        try:
            validate_playback_scenario(scenario)
        except ScenarioValidationError as error:
            raise SessionManagerError(str(error)) from error

        with self._session_factory.begin() as db:
            actor = require_role(db.get(User, actor_id), [Role.INSTRUCTOR, Role.ADMIN])
            trainee = db.get(User, trainee_id)
            if trainee is None or trainee.role != Role.TRAINEE.value:
                raise SessionManagerError("trainee_id must identify a trainee")
            _require_instructor_unit_access(actor, trainee)
            if db.get(TrainingSessionRecord, session_id) is not None:
                raise SessionManagerError("session_id already exists")
            _reject_seen_v1_fingerprint(db, trainee_id=trainee_id, scenario=scenario)
            _reject_semantically_similar_recent_v1_scenario(
                db,
                trainee_id=trainee_id,
                scenario=scenario,
            )
            assignment_sequence = (
                int(db.scalar(select(func.max(TrainingSessionRecord.assignment_sequence))) or 0) + 1
            )
            db.add(
                TrainingSessionRecord(
                    session_id=session_id,
                    scenario_id=str(scenario["scenario_id"]),
                    trainee_id=trainee_id,
                    scenario_json=canonical_json(scenario),
                    assignment_sequence=assignment_sequence,
                    selection_mode=selection_mode,
                    status=SessionStatus.ACTIVE.value,
                    rating_eligible=True,
                    rating_applied=False,
                    score_json=None,
                )
            )

    def ingest_event(self, *, actor_id: str, event: Mapping[str, Any]) -> EventIngestResult:
        """Validate and persist one trainee event with event-id idempotency."""
        try:
            validate_versioned_payload("event", event)
        except ContractValidationError as error:
            raise SessionManagerError(str(error)) from error

        event_json = canonical_json(event)
        event_id = str(event["event_id"])
        session_id = str(event["session_id"])
        with self._session_factory.begin() as db:
            actor = require_role(db.get(User, actor_id), [Role.TRAINEE])
            if actor.user_id != event["trainee_id"]:
                raise AuthorizationError("trainees may only submit their own events")

            existing_event = db.get(TraineeEventRecord, event_id)
            if existing_event is not None:
                if existing_event.event_json != event_json:
                    raise EventConflictError("event_id is already bound to a different payload")
                existing_session = _get_session(db, existing_event.session_id)
                return EventIngestResult(
                    event_id=event_id,
                    created=False,
                    session_status=existing_session.status,
                    rating_eligible=existing_session.rating_eligible,
                )

            training_session = _get_session(db, session_id)
            if training_session.trainee_id != actor.user_id:
                raise AuthorizationError("trainee does not own this session")
            if training_session.status != SessionStatus.ACTIVE.value:
                raise SessionManagerError("events may only be added to an active session")
            if event["scenario_id"] != training_session.scenario_id:
                raise SessionManagerError("event scenario_id does not match the session scenario")

            scenario = json.loads(training_session.scenario_json)
            if event["contract_version"] != scenario["contract_version"]:
                raise SessionManagerError(
                    "event contract_version does not match the session scenario"
                )
            _validate_event_against_scenario(event, scenario)
            duplicate_sequence = db.scalar(
                select(TraineeEventRecord).where(
                    TraineeEventRecord.session_id == session_id,
                    TraineeEventRecord.sequence == int(event["sequence"]),
                )
            )
            if duplicate_sequence is not None:
                raise SessionManagerError("event sequence is already used by this session")

            db.add(
                TraineeEventRecord(
                    event_id=event_id,
                    session_id=session_id,
                    sequence=int(event["sequence"]),
                    event_type=str(event["event_type"]),
                    t_offset_ms=int(event["t_offset_ms"]),
                    event_json=event_json,
                )
            )
            if event["event_type"] == "session_interrupted":
                training_session.status = SessionStatus.INTERRUPTED.value
                training_session.rating_eligible = False

            return EventIngestResult(
                event_id=event_id,
                created=True,
                session_status=training_session.status,
                rating_eligible=training_session.rating_eligible,
            )

    def complete_session(self, *, actor_id: str, session_id: str) -> None:
        """Mark an active session complete without using a wall-clock timestamp."""
        with self._session_factory.begin() as db:
            actor = _get_actor(db, actor_id)
            training_session = _get_session(db, session_id)
            _require_session_access(db, actor, training_session, allow_trainee_owner=True)
            if training_session.status == SessionStatus.INTERRUPTED.value:
                raise SessionManagerError("interrupted sessions cannot be completed")
            if training_session.status == SessionStatus.COMPLETED.value:
                return
            training_session.status = SessionStatus.COMPLETED.value

    def evaluate_session(
        self,
        *,
        actor_id: str,
        session_id: str,
        doctrine_path: Path | None = None,
        doctrine: Mapping[str, Any] | None = None,
    ) -> ScoreReport:
        """Score a completed/interrupted session and store its deterministic AAR."""
        if (doctrine_path is None) == (doctrine is None):
            raise SessionManagerError("provide exactly one doctrine path or doctrine payload")
        if doctrine is None:
            doctrine = load_doctrine(doctrine_path)
        else:
            validate_doctrine(doctrine)
        with self._session_factory.begin() as db:
            actor = _get_actor(db, actor_id)
            require_role(actor, [Role.INSTRUCTOR, Role.ADMIN])
            training_session = _get_session(db, session_id)
            _require_session_access(db, actor, training_session, allow_trainee_owner=False)
            if training_session.status == SessionStatus.ACTIVE.value:
                raise SessionManagerError(
                    "an active session must be completed or interrupted first"
                )

            events = [
                json.loads(row.event_json)
                for row in db.scalars(
                    select(TraineeEventRecord)
                    .where(TraineeEventRecord.session_id == session_id)
                    .order_by(TraineeEventRecord.sequence, TraineeEventRecord.event_id)
                )
            ]
            report = score_scenario(
                json.loads(training_session.scenario_json),
                events,
                doctrine,
                interrupted=not training_session.rating_eligible,
            )
            training_session.score_json = canonical_json(report.as_dict())
            return report

    def mark_rating_applied(self, *, actor_id: str, session_id: str) -> None:
        """Mark a scored eligible session consumed by the skill model exactly once."""
        with self._session_factory.begin() as db:
            actor = require_role(db.get(User, actor_id), [Role.INSTRUCTOR, Role.ADMIN])
            training_session = _get_session(db, session_id)
            _require_session_access(db, actor, training_session, allow_trainee_owner=False)
            if not training_session.rating_eligible:
                return
            if training_session.score_json is None:
                raise SessionManagerError("session must be scored before applying skill ratings")
            training_session.rating_applied = True

    def list_sessions(
        self,
        *,
        actor_id: str,
        trainee_id: str | None = None,
    ) -> tuple[SessionSummary, ...]:
        """List sessions visible to the requesting local role."""
        with self._session_factory() as db:
            actor = _get_actor(db, actor_id)
            visible_trainee_id = trainee_id
            if actor.role == Role.TRAINEE.value:
                if trainee_id is not None and trainee_id != actor.user_id:
                    raise AuthorizationError("trainees may only list their own sessions")
                visible_trainee_id = actor.user_id
            query = select(TrainingSessionRecord)
            if actor.role == Role.INSTRUCTOR.value:
                if visible_trainee_id is not None:
                    trainee = db.get(User, visible_trainee_id)
                    if trainee is None or trainee.role != Role.TRAINEE.value:
                        raise SessionManagerError("trainee_id must identify a trainee")
                    _require_instructor_unit_access(actor, trainee)
                query = query.join(User, TrainingSessionRecord.trainee_id == User.user_id).where(
                    User.unit_id == actor.unit_id
                )
            query = query.order_by(TrainingSessionRecord.session_id)
            if visible_trainee_id is not None:
                query = query.where(TrainingSessionRecord.trainee_id == visible_trainee_id)
            return tuple(
                SessionSummary(
                    session_id=row.session_id,
                    scenario_id=row.scenario_id,
                    trainee_id=row.trainee_id,
                    selection_mode=row.selection_mode,
                    status=row.status,
                    rating_eligible=row.rating_eligible,
                    total_score=(
                        float(json.loads(row.score_json).get("total_score", 0.0))
                        if row.score_json
                        else None
                    ),
                )
                for row in db.scalars(query)
            )

    def get_snapshot(self, *, actor_id: str, session_id: str) -> SessionSnapshot:
        """Read a session only if the actor is its trainee or instructional staff."""
        with self._session_factory() as db:
            actor = _get_actor(db, actor_id)
            training_session = _get_session(db, session_id)
            _require_session_access(db, actor, training_session, allow_trainee_owner=True)
            events = tuple(
                json.loads(row.event_json)
                for row in db.scalars(
                    select(TraineeEventRecord)
                    .where(TraineeEventRecord.session_id == session_id)
                    .order_by(TraineeEventRecord.sequence, TraineeEventRecord.event_id)
                )
            )
            score = json.loads(training_session.score_json) if training_session.score_json else None
            return SessionSnapshot(
                session_id=training_session.session_id,
                scenario=json.loads(training_session.scenario_json),
                trainee_id=training_session.trainee_id,
                selection_mode=training_session.selection_mode,
                status=training_session.status,
                rating_eligible=training_session.rating_eligible,
                rating_applied=training_session.rating_applied,
                events=events,
                score=score,
            )


def _get_actor(db: Session, actor_id: str) -> User:
    """Load an actor or raise the same authorization error as role checks."""
    return require_role(db.get(User, actor_id), [Role.TRAINEE, Role.INSTRUCTOR, Role.ADMIN])


def _get_session(db: Session, session_id: str) -> TrainingSessionRecord:
    training_session = db.get(TrainingSessionRecord, session_id)
    if training_session is None:
        raise SessionManagerError("session does not exist")
    return training_session


def _require_session_access(
    db: Session,
    actor: User,
    training_session: TrainingSessionRecord,
    *,
    allow_trainee_owner: bool,
) -> None:
    """Enforce trainee ownership and instructor-local-unit access."""
    if actor.role == Role.ADMIN.value:
        return
    if actor.role == Role.INSTRUCTOR.value:
        trainee = db.get(User, training_session.trainee_id)
        if trainee is not None:
            _require_instructor_unit_access(actor, trainee)
            return
        raise AuthorizationError("session trainee does not exist")
    is_own_trainee_session = (
        allow_trainee_owner
        and actor.role == Role.TRAINEE.value
        and actor.user_id == training_session.trainee_id
    )
    if is_own_trainee_session:
        return
    raise AuthorizationError("actor cannot access this session")


def _require_instructor_unit_access(actor: User, trainee: User) -> None:
    """Limit instructors to trainees assigned to their persisted local unit."""
    if actor.role == Role.INSTRUCTOR.value and actor.unit_id != trainee.unit_id:
        raise AuthorizationError("instructors may only access trainees in their own unit")


def _reject_seen_v1_fingerprint(
    db: Session,
    *,
    trainee_id: str,
    scenario: Mapping[str, Any],
) -> None:
    """Reject an exact prior V1 structure for one trainee without wall-clock state.

    Fixed scenarios can still be assigned across different trainees for fair
    unit comparisons. The check deliberately applies only to V1 procedural
    payloads and compares their deterministic structural fingerprint.
    """
    if scenario.get("generator_version") != GENERATOR_V1_VERSION:
        return
    candidate = scenario_fingerprint(scenario)
    prior_payloads = db.scalars(
        select(TrainingSessionRecord.scenario_json).where(
            TrainingSessionRecord.trainee_id == trainee_id
        )
    )
    for scenario_json in prior_payloads:
        prior = json.loads(scenario_json)
        if (
            prior.get("generator_version") == GENERATOR_V1_VERSION
            and scenario_fingerprint(prior) == candidate
        ):
            raise SessionManagerError(
                "V1 scenario repeats a prior structural fingerprint for this trainee"
            )


def _reject_semantically_similar_recent_v1_scenario(
    db: Session,
    *,
    trainee_id: str,
    scenario: Mapping[str, Any],
) -> None:
    """Apply the explicit local feature-signature rule to a trainee's last N.

    The query orders by persisted assignment sequence rather than wall-clock
    time. This fulfills a bounded recent-history policy deterministically even
    when the local machine clock is unavailable or incorrect.
    """
    if scenario.get("generator_version") != GENERATOR_V1_VERSION:
        return
    recent_records = db.scalars(
        select(TrainingSessionRecord.scenario_json)
        .where(TrainingSessionRecord.trainee_id == trainee_id)
        .order_by(TrainingSessionRecord.assignment_sequence.desc())
        .limit(DEFAULT_SEMANTIC_NOVELTY_POLICY.recent_session_count)
    )
    recent_scenarios = [json.loads(scenario_json) for scenario_json in recent_records]
    similarity = most_similar_recent_scenario(scenario, recent_scenarios)
    if similarity is not None and similarity >= DEFAULT_SEMANTIC_NOVELTY_POLICY.maximum_similarity:
        raise SessionManagerError(
            "V1 scenario is semantically too similar to one of the trainee's "
            f"last {DEFAULT_SEMANTIC_NOVELTY_POLICY.recent_session_count} scenarios "
            f"(Jaccard similarity {similarity:.3f})"
        )


def _validate_event_against_scenario(event: Mapping[str, Any], scenario: Mapping[str, Any]) -> None:
    """Ensure client logical time and target reference stay inside playback data."""
    if int(event["t_offset_ms"]) > int(scenario["duration_ms"]):
        raise SessionManagerError("event t_offset_ms exceeds scenario duration")
    if event["event_type"] == "session_interrupted":
        return
    target_ids = {target["target_id"] for target in scenario["targets"]}
    if event["payload"]["target_id"] not in target_ids:
        raise SessionManagerError("event target_id does not exist in the scenario")


def _validate_user_id(user_id: str) -> None:
    if not isinstance(user_id, str) or not USER_ID_PATTERN.fullmatch(user_id):
        raise SessionManagerError("user_id must match the local identifier contract")


def _validate_unit_id(unit_id: str) -> None:
    if not isinstance(unit_id, str) or not UNIT_ID_PATTERN.fullmatch(unit_id):
        raise SessionManagerError("unit_id must match the local identifier contract")


def _validate_session_id(session_id: str) -> None:
    try:
        UUID(session_id)
    except (AttributeError, ValueError) as error:
        raise SessionManagerError("session_id must be a UUID") from error
