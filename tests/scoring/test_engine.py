"""Hand-checked generic-demo scoring tests (not Blueprint G1–G10 fixtures)."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest

from core.generator import ScenarioProfile, generate_scenario
from core.scoring import (
    DoctrineValidationError,
    ScoringError,
    load_doctrine,
    score_scenario,
    validate_doctrine,
)

PROFILE = ScenarioProfile(
    profile_id="score-single-target",
    difficulty=1,
    skill_tags=("detection", "classification", "assessment", "response"),
)
DOCTRINE_PATH = Path(__file__).resolve().parents[2] / "doctrine" / "generic_demo.yaml"
SESSION_ID = "11111111-1111-4111-8111-111111111111"


def _event(
    scenario: dict[str, object],
    *,
    action: str,
    sequence: int,
    t_offset_ms: int,
    value: str | None = None,
) -> dict[str, object]:
    target_id = str(scenario["targets"][0]["target_id"])
    payload: dict[str, object] = {"target_id": target_id}
    if action == "classify":
        payload["classification"] = value
    elif action == "assess":
        payload["assessment"] = value
    elif action == "respond":
        payload["response"] = value
    elif action == "session_interrupted":
        payload = {"reason": "user_exit"}

    return {
        "contract_version": "1.0",
        "event_id": str(uuid5(NAMESPACE_URL, f"{action}-{sequence}-{t_offset_ms}-{value}")),
        "session_id": SESSION_ID,
        "scenario_id": scenario["scenario_id"],
        "trainee_id": "trainee-001",
        "event_type": action,
        "t_offset_ms": t_offset_ms,
        "sequence": sequence,
        "payload": payload,
    }


def _scenario() -> dict[str, object]:
    return generate_scenario(23, PROFILE)


def test_generic_demo_full_correct_path_scores_100() -> None:
    scenario = _scenario()
    visible_at = int(scenario["targets"][0]["t_visible_ms"])
    doctrine = load_doctrine(DOCTRINE_PATH)
    events = [
        _event(scenario, action="detect", sequence=0, t_offset_ms=visible_at),
        _event(
            scenario,
            action="classify",
            sequence=1,
            t_offset_ms=visible_at + 200,
            value="simulated_threat",
        ),
        _event(scenario, action="assess", sequence=2, t_offset_ms=visible_at + 400, value="high"),
        _event(
            scenario, action="respond", sequence=3, t_offset_ms=visible_at + 600, value="report"
        ),
    ]

    report = score_scenario(scenario, events, doctrine)

    assert report.total_score == 100.0
    assert [result.points for result in report.node_results] == [40.0, 25.0, 20.0, 15.0]
    assert report.rating_eligible is True


def test_detection_delay_is_measured_from_t_visible_not_scenario_start() -> None:
    scenario = _scenario()
    visible_at = int(scenario["targets"][0]["t_visible_ms"])
    doctrine = load_doctrine(DOCTRINE_PATH)

    report = score_scenario(
        scenario,
        [_event(scenario, action="detect", sequence=0, t_offset_ms=visible_at)],
        doctrine,
    )
    detection = report.node_results[0]

    assert detection.detection_delay_ms == 0
    assert detection.timing_band == "excellent"
    assert detection.points == 40.0


def test_generic_demo_late_detection_has_hand_computed_partial_credit() -> None:
    scenario = _scenario()
    visible_at = int(scenario["targets"][0]["t_visible_ms"])
    doctrine = load_doctrine(DOCTRINE_PATH)

    report = score_scenario(
        scenario,
        [_event(scenario, action="detect", sequence=0, t_offset_ms=visible_at + 6_000)],
        doctrine,
    )

    # (late_ms - delay) / (late_ms - excellent_ms) = (8000 - 6000) / (8000 - 2000)
    assert report.total_score == pytest.approx(13.333333)
    assert report.node_results[0].timing_band == "late"


def test_incorrect_classification_keeps_other_generic_nodes_scoreable() -> None:
    scenario = _scenario()
    visible_at = int(scenario["targets"][0]["t_visible_ms"])
    doctrine = load_doctrine(DOCTRINE_PATH)
    events = [
        _event(scenario, action="detect", sequence=0, t_offset_ms=visible_at),
        _event(scenario, action="classify", sequence=1, t_offset_ms=visible_at + 100, value="bird"),
        _event(scenario, action="assess", sequence=2, t_offset_ms=visible_at + 200, value="high"),
        _event(
            scenario, action="respond", sequence=3, t_offset_ms=visible_at + 300, value="report"
        ),
    ]

    report = score_scenario(scenario, events, doctrine)

    assert report.total_score == 75.0
    assert [result.outcome for result in report.node_results] == [
        "correct",
        "incorrect",
        "correct",
        "correct",
    ]


def test_score_scenario_deduplicates_identical_event_retries() -> None:
    scenario = _scenario()
    visible_at = int(scenario["targets"][0]["t_visible_ms"])
    doctrine = load_doctrine(DOCTRINE_PATH)
    detect = _event(scenario, action="detect", sequence=0, t_offset_ms=visible_at)

    once = score_scenario(scenario, [detect], doctrine)
    retried = score_scenario(scenario, [detect, dict(detect)], doctrine)

    assert retried == once


def test_score_scenario_rejects_conflicting_event_id_reuse() -> None:
    scenario = _scenario()
    visible_at = int(scenario["targets"][0]["t_visible_ms"])
    doctrine = load_doctrine(DOCTRINE_PATH)
    detect = _event(scenario, action="detect", sequence=0, t_offset_ms=visible_at)
    conflicting = dict(detect)
    conflicting["t_offset_ms"] = visible_at + 100

    with pytest.raises(ScoringError, match="event_id is already bound"):
        score_scenario(scenario, [detect, conflicting], doctrine)


def test_interruption_event_marks_report_ineligible_for_skill_rating() -> None:
    scenario = _scenario()
    visible_at = int(scenario["targets"][0]["t_visible_ms"])
    doctrine = load_doctrine(DOCTRINE_PATH)
    events = [
        _event(scenario, action="detect", sequence=0, t_offset_ms=visible_at),
        _event(scenario, action="session_interrupted", sequence=1, t_offset_ms=visible_at + 100),
    ]

    report = score_scenario(scenario, events, doctrine)

    assert report.interrupted is True
    assert report.rating_eligible is False
    assert report.total_score == 40.0


def test_score_contributions_follow_the_doctrine_weights() -> None:
    scenario = _scenario()
    visible_at = int(scenario["targets"][0]["t_visible_ms"])
    doctrine = deepcopy(load_doctrine(DOCTRINE_PATH))
    doctrine["scoring"]["weights"] = {
        "detect": 0.10,
        "classify": 0.40,
        "assess": 0.30,
        "respond": 0.20,
    }
    events = [
        _event(scenario, action="detect", sequence=0, t_offset_ms=visible_at),
        _event(
            scenario,
            action="classify",
            sequence=1,
            t_offset_ms=visible_at + 100,
            value="simulated_threat",
        ),
        _event(scenario, action="assess", sequence=2, t_offset_ms=visible_at + 200, value="high"),
        _event(
            scenario, action="respond", sequence=3, t_offset_ms=visible_at + 300, value="report"
        ),
    ]

    report = score_scenario(scenario, events, doctrine)

    assert [result.points for result in report.node_results] == [10.0, 40.0, 30.0, 20.0]


def test_doctrine_weights_must_come_from_a_semantically_valid_doctrine() -> None:
    doctrine = deepcopy(load_doctrine(DOCTRINE_PATH))
    doctrine["scoring"]["weights"]["detect"] = 0.9

    with pytest.raises(DoctrineValidationError, match="sum to 1.0"):
        validate_doctrine(doctrine)
