"""Native production contract-v2 execution for the proposed G1–G10 pack.

The YAML fixtures are already nested v2 scenario/event/doctrine payloads. This
module calls ``score_scenario`` directly: no reference scorer or scoring sidecar
participates in these assertions.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from core.db import Role, create_session_factory, create_sqlite_engine, initialize_database
from core.scoring import DoctrineRepository, DoctrineValidationError, load_doctrine, score_scenario
from core.sessions import SessionManager

GOLDEN_DIR = Path(__file__).resolve().parent
DOCTRINE_PATH = GOLDEN_DIR / "doctrine_generic_demo_v2.yaml"
DOCTRINE = load_doctrine(DOCTRINE_PATH)
CASES = yaml.safe_load((GOLDEN_DIR / "golden_cases_v2.yaml").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("golden_id", [f"G{index}" for index in range(1, 10)])
def test_native_v2_production_scorer_matches_proposed_golden_expectations(golden_id: str) -> None:
    case = CASES[golden_id]
    assert case["scenario"]["contract_version"] == "2.0"
    assert all(event["contract_version"] == "2.0" for event in case["events"])

    report = score_scenario(
        case["scenario"],
        case["events"],
        DOCTRINE,
        interrupted=case["status"] == "interrupted",
    )

    expected = case["expect"]
    assert report.total_score == pytest.approx(expected["total"], abs=0.01)
    assert list(report.critical_errors) == expected["critical"]
    assert report.ignored_duplicate_events == expected["ignored_duplicates"]
    assert report.rating_eligible is expected["rating_eligible"]
    assert {
        result.target_id: result.score_fraction for result in report.target_results
    } == pytest.approx(expected["per_target"], abs=0.001)


def test_g5_v2_detection_delay_is_relative_to_visibility() -> None:
    case = CASES["G5"]
    report = score_scenario(case["scenario"], case["events"], DOCTRINE)

    detection = next(
        result
        for result in report.node_results
        if result.action == "detect" and result.target_id == "h1"
    )
    assert detection.detection_delay_ms == 12_000


def test_g8_v2_duplicate_ids_are_natively_ignored_once() -> None:
    case = CASES["G8"]
    report = score_scenario(case["scenario"], case["events"], DOCTRINE)

    assert report.ignored_duplicate_events == 3
    assert report.total_score == pytest.approx(98.5, abs=0.01)
    assert len(report.node_results) == 4


def test_native_v2_session_lifecycle_persists_the_production_score(tmp_path: Path) -> None:
    case = CASES["G1"]
    engine = create_sqlite_engine(tmp_path / "v2-session.sqlite3")
    initialize_database(engine)
    factory = create_session_factory(engine)
    sessions = SessionManager(factory)
    sessions.create_bootstrap_admin("admin-001", "1234")
    sessions.create_user(
        actor_id="admin-001",
        user_id="instructor-001",
        role=Role.INSTRUCTOR,
        pin="2345",
    )
    sessions.create_user(
        actor_id="admin-001",
        user_id="golden-trainee",
        role=Role.TRAINEE,
        pin="3456",
    )
    session_id = case["events"][0]["session_id"]
    sessions.create_training_session(
        actor_id="instructor-001",
        session_id=session_id,
        trainee_id="golden-trainee",
        scenario=case["scenario"],
    )
    for event in case["events"]:
        sessions.ingest_event(actor_id="golden-trainee", event=event)
    sessions.complete_session(actor_id="golden-trainee", session_id=session_id)

    report = sessions.evaluate_session(
        actor_id="instructor-001",
        session_id=session_id,
        doctrine=DOCTRINE,
    )
    snapshot = sessions.get_snapshot(actor_id="instructor-001", session_id=session_id)
    assert report.total_score == pytest.approx(98.5, abs=0.01)
    assert snapshot.score is not None
    assert snapshot.score["total_score"] == pytest.approx(98.5, abs=0.01)


def test_g10_v2_invalid_doctrine_is_rejected_without_replacing_active_record(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(tmp_path / "trainer.sqlite3")
    initialize_database(engine)
    factory = create_session_factory(engine)
    sessions = SessionManager(factory)
    sessions.create_bootstrap_admin("admin-001", "1234")
    repository = DoctrineRepository(factory)
    valid_text = DOCTRINE_PATH.read_text(encoding="utf-8")
    repository.upload(actor_id="admin-001", yaml_text=valid_text)

    invalid = deepcopy(DOCTRINE)
    invalid["scoring"]["weights"] = CASES["G10"]["invalid_doctrine_override"]["scoring"]["weights"]
    invalid_text = yaml.safe_dump(invalid, sort_keys=False)
    with pytest.raises(DoctrineValidationError, match="weights must sum"):
        repository.upload(actor_id="admin-001", yaml_text=invalid_text)

    active = repository.get(
        actor_id="admin-001",
        doctrine_id=DOCTRINE["doctrine_id"],
        version=DOCTRINE["version"],
    )
    assert active == DOCTRINE
