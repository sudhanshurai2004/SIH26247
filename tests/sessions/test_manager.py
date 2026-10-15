"""SQLite session, role, PIN, interruption, and idempotency tests."""

from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest
from sqlalchemy.orm import sessionmaker

from core.db import (
    AuthorizationError,
    Role,
    SessionStatus,
    User,
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)
from core.generator import ScenarioProfile, generate_scenario
from core.sessions import EventConflictError, SessionManager, SessionManagerError

PROFILE = ScenarioProfile(
    profile_id="session-single-target",
    difficulty=1,
    skill_tags=("detection", "classification", "assessment", "response"),
)
DOCTRINE_PATH = Path(__file__).resolve().parents[2] / "doctrine" / "generic_demo.yaml"


@pytest.fixture
def manager(tmp_path: Path) -> tuple[SessionManager, sessionmaker]:
    engine = create_sqlite_engine(tmp_path / "trainer.sqlite3")
    initialize_database(engine)
    factory = create_session_factory(engine)
    service = SessionManager(factory)
    service.create_bootstrap_admin("admin-001", "1234")
    service.create_user(
        actor_id="admin-001",
        user_id="instructor-001",
        role=Role.INSTRUCTOR,
        pin="2345",
    )
    service.create_user(
        actor_id="admin-001",
        user_id="trainee-001",
        role=Role.TRAINEE,
        pin="3456",
    )
    service.create_user(
        actor_id="admin-001",
        user_id="trainee-002",
        role=Role.TRAINEE,
        pin="4567",
    )
    return service, factory


def _session_id(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"session-{name}"))


def _event(
    scenario: dict[str, object],
    *,
    session_id: str,
    action: str,
    sequence: int,
    t_offset_ms: int,
    event_id: str | None = None,
) -> dict[str, object]:
    target_id = str(scenario["targets"][0]["target_id"])
    payload: dict[str, object] = {"target_id": target_id}
    if action == "classify":
        payload["classification"] = "simulated_threat"
    elif action == "assess":
        payload["assessment"] = "high"
    elif action == "respond":
        payload["response"] = "report"
    elif action == "session_interrupted":
        payload = {"reason": "application_error"}

    return {
        "contract_version": "1.0",
        "event_id": event_id
        or str(uuid5(NAMESPACE_URL, f"event-{session_id}-{action}-{sequence}-{t_offset_ms}")),
        "session_id": session_id,
        "scenario_id": scenario["scenario_id"],
        "trainee_id": "trainee-001",
        "event_type": action,
        "t_offset_ms": t_offset_ms,
        "sequence": sequence,
        "payload": payload,
    }


def _assigned_scenario() -> dict[str, object]:
    return generate_scenario(55, PROFILE)


def _create_session(manager: SessionManager, scenario: dict[str, object], session_id: str) -> None:
    manager.create_training_session(
        actor_id="instructor-001",
        session_id=session_id,
        trainee_id="trainee-001",
        scenario=scenario,
    )


def test_pins_are_hashed_and_admin_role_is_required(
    manager: tuple[SessionManager, sessionmaker],
) -> None:
    service, factory = manager
    with factory() as db:
        trainee = db.get(User, "trainee-001")
        assert trainee is not None
        assert trainee.pin_hash != "3456"
        assert trainee.pin_hash.startswith("pbkdf2_sha256$")

    assert service.authenticate_pin("trainee-001", "3456") is True
    assert service.authenticate_pin("trainee-001", "0000") is False

    with pytest.raises(AuthorizationError):
        service.create_user(
            actor_id="trainee-001",
            user_id="trainee-003",
            role=Role.TRAINEE,
            pin="5678",
        )


def test_event_ingestion_is_idempotent_by_event_id(
    manager: tuple[SessionManager, sessionmaker],
) -> None:
    service, _ = manager
    scenario = _assigned_scenario()
    session_id = _session_id("idempotent")
    _create_session(service, scenario, session_id)
    event = _event(
        scenario,
        session_id=session_id,
        action="detect",
        sequence=0,
        t_offset_ms=int(scenario["targets"][0]["t_visible_ms"]),
    )

    first = service.ingest_event(actor_id="trainee-001", event=event)
    second = service.ingest_event(actor_id="trainee-001", event=event)
    snapshot = service.get_snapshot(actor_id="instructor-001", session_id=session_id)

    assert first.created is True
    assert second.created is False
    assert len(snapshot.events) == 1


def test_reusing_an_event_id_with_different_content_is_rejected(
    manager: tuple[SessionManager, sessionmaker],
) -> None:
    service, _ = manager
    scenario = _assigned_scenario()
    session_id = _session_id("conflict")
    _create_session(service, scenario, session_id)
    event = _event(scenario, session_id=session_id, action="detect", sequence=0, t_offset_ms=4_000)
    service.ingest_event(actor_id="trainee-001", event=event)
    changed_event = dict(event)
    changed_event["t_offset_ms"] = 5_000

    with pytest.raises(EventConflictError, match="different payload"):
        service.ingest_event(actor_id="trainee-001", event=changed_event)


def test_event_sequence_must_be_unique_within_a_session(
    manager: tuple[SessionManager, sessionmaker],
) -> None:
    service, _ = manager
    scenario = _assigned_scenario()
    session_id = _session_id("sequence")
    _create_session(service, scenario, session_id)
    service.ingest_event(
        actor_id="trainee-001",
        event=_event(
            scenario, session_id=session_id, action="detect", sequence=0, t_offset_ms=4_000
        ),
    )

    with pytest.raises(SessionManagerError, match="sequence"):
        service.ingest_event(
            actor_id="trainee-001",
            event=_event(
                scenario,
                session_id=session_id,
                action="classify",
                sequence=0,
                t_offset_ms=4_100,
            ),
        )


def test_interrupted_session_is_marked_and_excluded_from_rating(
    manager: tuple[SessionManager, sessionmaker],
) -> None:
    service, _ = manager
    scenario = _assigned_scenario()
    session_id = _session_id("interrupted")
    _create_session(service, scenario, session_id)
    interruption = _event(
        scenario,
        session_id=session_id,
        action="session_interrupted",
        sequence=0,
        t_offset_ms=1_000,
    )

    result = service.ingest_event(actor_id="trainee-001", event=interruption)
    snapshot = service.get_snapshot(actor_id="instructor-001", session_id=session_id)
    report = service.evaluate_session(
        actor_id="instructor-001",
        session_id=session_id,
        doctrine_path=DOCTRINE_PATH,
    )

    assert result.session_status == SessionStatus.INTERRUPTED.value
    assert result.rating_eligible is False
    assert snapshot.status == SessionStatus.INTERRUPTED.value
    assert snapshot.rating_eligible is False
    assert report.rating_eligible is False

    with pytest.raises(SessionManagerError, match="active session"):
        service.ingest_event(
            actor_id="trainee-001",
            event=_event(
                scenario, session_id=session_id, action="detect", sequence=1, t_offset_ms=4_000
            ),
        )


def test_trainees_cannot_assign_or_access_another_trainees_session(
    manager: tuple[SessionManager, sessionmaker],
) -> None:
    service, _ = manager
    scenario = _assigned_scenario()
    session_id = _session_id("ownership")

    with pytest.raises(AuthorizationError):
        service.create_training_session(
            actor_id="trainee-001",
            session_id=session_id,
            trainee_id="trainee-001",
            scenario=scenario,
        )

    _create_session(service, scenario, session_id)
    event = _event(scenario, session_id=session_id, action="detect", sequence=0, t_offset_ms=4_000)
    event["trainee_id"] = "trainee-002"

    with pytest.raises(AuthorizationError, match="does not own"):
        service.ingest_event(actor_id="trainee-002", event=event)


def test_completed_session_scores_and_persists_a_replay_snapshot(
    manager: tuple[SessionManager, sessionmaker],
) -> None:
    service, _ = manager
    scenario = _assigned_scenario()
    session_id = _session_id("completed")
    visible_at = int(scenario["targets"][0]["t_visible_ms"])
    _create_session(service, scenario, session_id)
    for action, sequence, offset in [
        ("detect", 0, visible_at),
        ("classify", 1, visible_at + 100),
        ("assess", 2, visible_at + 200),
        ("respond", 3, visible_at + 300),
    ]:
        service.ingest_event(
            actor_id="trainee-001",
            event=_event(
                scenario,
                session_id=session_id,
                action=action,
                sequence=sequence,
                t_offset_ms=offset,
            ),
        )

    service.complete_session(actor_id="trainee-001", session_id=session_id)
    report = service.evaluate_session(
        actor_id="instructor-001",
        session_id=session_id,
        doctrine_path=DOCTRINE_PATH,
    )
    snapshot = service.get_snapshot(actor_id="trainee-001", session_id=session_id)

    assert report.total_score == 100.0
    assert snapshot.status == SessionStatus.COMPLETED.value
    assert snapshot.score is not None
    assert snapshot.score["total_score"] == 100.0
