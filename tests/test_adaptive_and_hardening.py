"""Adaptive selection, doctrine upload, trends, and backup tests."""

from __future__ import annotations

import sqlite3
from copy import deepcopy
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest
from sqlalchemy import inspect

from core.adaptive import (
    ScenarioOption,
    SkillModel,
    select_next_scenario,
    unit_summary,
    unit_trends,
)
from core.db import (
    AuthorizationError,
    Role,
    backup_sqlite_database,
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)
from core.generator import (
    ScenarioProfile,
    ScenarioV1Profile,
    generate_scenario,
    generate_scenario_v1,
)
from core.scoring import DoctrineRepository, DoctrineValidationError, load_doctrine, score_scenario
from core.sessions import SessionManager, SessionManagerError

DOCTRINE_PATH = Path(__file__).resolve().parents[1] / "doctrine" / "generic_demo.yaml"


def _service(tmp_path: Path) -> tuple[SessionManager, object, Path]:
    database_path = tmp_path / "trainer.sqlite3"
    engine = create_sqlite_engine(database_path)
    initialize_database(engine)
    factory = create_session_factory(engine)
    manager = SessionManager(factory)
    manager.create_bootstrap_admin("admin-001", "1234")
    manager.create_user(
        actor_id="admin-001",
        user_id="instructor-001",
        role=Role.INSTRUCTOR,
        pin="2345",
    )
    manager.create_user(
        actor_id="admin-001",
        user_id="trainee-001",
        role=Role.TRAINEE,
        pin="3456",
    )
    return manager, factory, database_path


def _full_report() -> object:
    scenario = generate_scenario(
        71,
        ScenarioProfile("adaptive-target", 2, ("detection", "classification")),
    )
    visible_at = scenario["targets"][0]["t_visible_ms"]
    target_id = scenario["targets"][0]["target_id"]
    session_id = "22222222-2222-4222-8222-222222222222"

    def event(event_type: str, sequence: int, payload: dict[str, str]) -> dict[str, object]:
        return {
            "contract_version": "1.0",
            "event_id": str(uuid5(NAMESPACE_URL, f"adaptive-{event_type}-{sequence}")),
            "session_id": session_id,
            "scenario_id": scenario["scenario_id"],
            "trainee_id": "trainee-001",
            "event_type": event_type,
            "t_offset_ms": visible_at + sequence * 100,
            "sequence": sequence,
            "payload": payload,
        }

    events = [
        event("detect", 0, {"target_id": target_id}),
        event("classify", 1, {"target_id": target_id, "classification": "simulated_threat"}),
        event("assess", 2, {"target_id": target_id, "assessment": "high"}),
        event("respond", 3, {"target_id": target_id, "response": "report"}),
    ]
    return score_scenario(scenario, events, load_doctrine(DOCTRINE_PATH))


def test_skill_model_updates_eligible_reports_and_skips_interrupted(tmp_path: Path) -> None:
    _, factory, _ = _service(tmp_path)
    model = SkillModel(factory)
    report = _full_report()

    updates = model.update_from_report(
        actor_id="instructor-001",
        trainee_id="trainee-001",
        report=report,
        difficulty=2,
    )

    assert {update.skill_tag for update in updates} == {
        "detection",
        "classification",
        "assessment",
        "response",
    }
    assert model.ratings_for(actor_id="trainee-001", trainee_id="trainee-001")

    interrupted = score_scenario(
        generate_scenario(72, ScenarioProfile("interrupt-target", 1, ("detection",))),
        [],
        load_doctrine(DOCTRINE_PATH),
        interrupted=True,
    )
    assert (
        model.update_from_report(
            actor_id="instructor-001",
            trainee_id="trainee-001",
            report=interrupted,
            difficulty=1,
        )
        == ()
    )


def test_skill_model_consumes_a_scored_session_only_once(tmp_path: Path) -> None:
    manager, factory, _ = _service(tmp_path)
    model = SkillModel(factory)
    scenario = generate_scenario(73, ScenarioProfile("rating-once", 2, ("detection",)))
    session_id = "23232323-2323-4232-8232-232323232323"
    manager.create_training_session(
        actor_id="instructor-001",
        session_id=session_id,
        trainee_id="trainee-001",
        scenario=scenario,
    )
    manager.complete_session(actor_id="trainee-001", session_id=session_id)
    report = manager.evaluate_session(
        actor_id="instructor-001",
        session_id=session_id,
        doctrine_path=DOCTRINE_PATH,
    )

    first = model.apply_session_report_once(
        actor_id="instructor-001", session_id=session_id, report=report, difficulty=2
    )
    second = model.apply_session_report_once(
        actor_id="instructor-001", session_id=session_id, report=report, difficulty=2
    )

    assert first
    assert second == ()


def test_selector_targets_lowest_rated_skill_with_stable_tie_break() -> None:
    choice = select_next_scenario(
        [
            ScenarioOption("classification-drill", 2, ("classification",)),
            ScenarioOption("detection-drill", 1, ("detection",)),
        ],
        {"classification": 1_100.0, "detection": 850.0},
    )

    assert choice.profile_id == "detection-drill"


def test_doctrine_upload_is_validated_and_idempotent(tmp_path: Path) -> None:
    manager, factory, _ = _service(tmp_path)
    repository = DoctrineRepository(factory)
    yaml_text = DOCTRINE_PATH.read_text(encoding="utf-8")

    first = repository.upload(actor_id="instructor-001", yaml_text=yaml_text)
    second = repository.upload(actor_id="instructor-001", yaml_text=yaml_text)

    assert first.created is True
    assert second.created is False
    active_doctrine = repository.get(
        actor_id="trainee-001",
        doctrine_id="generic-demo-v1",
        version="1.0.0",
    )
    assert active_doctrine["doctrine_id"] == "generic-demo-v1"
    with pytest.raises(DoctrineValidationError):
        repository.upload(
            actor_id="instructor-001", yaml_text="!!python/object/apply:os.system ['x']"
        )
    with pytest.raises(DoctrineValidationError, match="weights must sum"):
        repository.upload(
            actor_id="instructor-001",
            yaml_text=yaml_text.replace("detect: 0.40", "detect: 0.45"),
        )
    # G10 equivalent: validation fails before the existing active record is replaced.
    assert (
        repository.get(
            actor_id="trainee-001",
            doctrine_id="generic-demo-v1",
            version="1.0.0",
        )
        == active_doctrine
    )
    with pytest.raises(AuthorizationError):
        repository.upload(actor_id="trainee-001", yaml_text=yaml_text)
    assert manager.authenticate_pin("admin-001", "1234")


def test_database_initialization_adds_later_columns_to_a_stage2_database(tmp_path: Path) -> None:
    database_path = tmp_path / "stage2.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        CREATE TABLE users (user_id TEXT PRIMARY KEY, role TEXT NOT NULL, pin_hash TEXT NOT NULL);
        CREATE TABLE training_sessions (
            session_id TEXT PRIMARY KEY,
            scenario_id TEXT NOT NULL,
            trainee_id TEXT NOT NULL,
            scenario_json TEXT NOT NULL,
            status TEXT NOT NULL,
            rating_eligible BOOLEAN NOT NULL,
            score_json TEXT
        );
        """
    )
    connection.close()

    engine = create_sqlite_engine(database_path)
    initialize_database(engine)

    session_columns = {
        column["name"] for column in inspect(engine).get_columns("training_sessions")
    }
    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    assert {"assignment_sequence", "selection_mode", "rating_applied"}.issubset(session_columns)
    assert "unit_id" in user_columns


def test_backup_uses_controlled_local_destination(tmp_path: Path) -> None:
    _, _, database_path = _service(tmp_path)

    backup_path = backup_sqlite_database(database_path, tmp_path / "backups", "pilot_01")

    assert backup_path.is_file()
    assert backup_path.parent == tmp_path / "backups"


def test_v1_novelty_rejects_a_repeat_for_same_trainee_but_not_other_trainees(
    tmp_path: Path,
) -> None:
    manager, _, _ = _service(tmp_path)
    manager.create_user(
        actor_id="admin-001",
        user_id="trainee-002",
        role=Role.TRAINEE,
        pin="4567",
    )
    scenario = generate_scenario_v1(
        91,
        ScenarioV1Profile("novelty-session", 2, ("detection",), swarm_size=3, clutter_count=1),
    )
    manager.create_training_session(
        actor_id="instructor-001",
        session_id="91919191-9191-4191-8191-919191919191",
        trainee_id="trainee-001",
        scenario=scenario,
        selection_mode="adaptive",
    )

    with pytest.raises(SessionManagerError, match="fingerprint"):
        manager.create_training_session(
            actor_id="instructor-001",
            session_id="92929292-9292-4292-8292-929292929292",
            trainee_id="trainee-001",
            scenario=scenario,
            selection_mode="adaptive",
        )

    manager.create_training_session(
        actor_id="instructor-001",
        session_id="93939393-9393-4393-8393-939393939393",
        trainee_id="trainee-002",
        scenario=scenario,
        selection_mode="adaptive",
    )


def test_v1_semantic_novelty_checks_only_the_persisted_last_n_sessions(tmp_path: Path) -> None:
    manager, _, _ = _service(tmp_path)
    profile = ScenarioV1Profile(
        "semantic-window",
        2,
        ("detection",),
        swarm_size=3,
        clutter_count=1,
    )
    oldest = generate_scenario_v1(91, profile)
    manager.create_training_session(
        actor_id="instructor-001",
        session_id="91919191-9191-4191-8191-919191919191",
        trainee_id="trainee-001",
        scenario=oldest,
        selection_mode="adaptive",
    )

    recent_clone = deepcopy(oldest)
    recent_clone["scenario_id"] = "scenario-v1-semantic-recent-clone"
    recent_clone["targets"][0]["trajectory"][1]["x_m"] += 0.001
    with pytest.raises(SessionManagerError, match="semantically too similar"):
        manager.create_training_session(
            actor_id="instructor-001",
            session_id="92929292-9292-4292-8292-929292929292",
            trainee_id="trainee-001",
            scenario=recent_clone,
            selection_mode="adaptive",
        )

    for offset, seed in enumerate(range(92, 97), start=3):
        manager.create_training_session(
            actor_id="instructor-001",
            session_id=f"{offset}{offset}{offset}{offset}{offset}{offset}{offset}{offset}-"
            f"{offset}{offset}{offset}{offset}-4{offset}{offset}{offset}-8{offset}{offset}{offset}-"
            f"{offset:012d}",
            trainee_id="trainee-001",
            scenario=generate_scenario_v1(seed, profile),
            selection_mode="adaptive",
        )

    # It is a semantic clone of the oldest record, but it falls outside the
    # deterministic last-five window and is not an exact fingerprint repeat.
    manager.create_training_session(
        actor_id="instructor-001",
        session_id="98989898-9898-4898-8898-989898989898",
        trainee_id="trainee-001",
        scenario=recent_clone,
        selection_mode="adaptive",
    )


def test_unit_trends_returns_only_real_scored_sessions(tmp_path: Path) -> None:
    manager, factory, _ = _service(tmp_path)
    scenario = generate_scenario(88, ScenarioProfile("trend-target", 1, ("detection",)))
    session_id = "33333333-3333-4333-8333-333333333333"
    manager.create_training_session(
        actor_id="instructor-001",
        session_id=session_id,
        trainee_id="trainee-001",
        scenario=scenario,
        selection_mode="adaptive",
    )
    manager.complete_session(actor_id="trainee-001", session_id=session_id)
    manager.evaluate_session(
        actor_id="instructor-001",
        session_id=session_id,
        doctrine_path=DOCTRINE_PATH,
    )

    trends = unit_trends(session_factory=factory, actor_id="instructor-001")

    assert trends[0].selection_mode == "adaptive"
    assert trends[0].completed_sessions == 1

    summary = unit_summary(
        session_factory=factory,
        actor_id="instructor-001",
        unit_id="local-unit",
    )
    assert summary.unit_id == "local-unit"
    assert summary.trainees[0].trainee_id == "trainee-001"
    assert summary.trainees[0].completed_sessions == 1
