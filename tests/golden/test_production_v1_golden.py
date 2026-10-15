"""Run the proposed G1–G10 cases through valid v1 payloads and score_scenario."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import reference_scorer as reference_scorer
import yaml

from core.scoring import load_proposed_golden_doctrine, score_proposed_golden_case_with_v1

GOLDEN_DIR = Path(__file__).resolve().parent
DOCTRINE = load_proposed_golden_doctrine(GOLDEN_DIR / "doctrine_generic_demo_v1.yaml")
CASES: dict[str, dict[str, Any]] = yaml.safe_load(
    (GOLDEN_DIR / "golden_cases.yaml").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("golden_id", [f"G{index}" for index in range(1, 10)])
def test_v1_adapter_runs_proposed_golden_case_through_production_scorer(golden_id: str) -> None:
    case = CASES[golden_id]
    reference = reference_scorer.score(DOCTRINE, case["targets"], case["events"], case["status"])

    result = score_proposed_golden_case_with_v1(
        golden_id,
        DOCTRINE,
        case["targets"],
        case["events"],
        status=case["status"],
    )

    assert result.total == pytest.approx(reference["total"], abs=0.01)
    assert list(result.critical) == reference["critical"]
    assert result.ignored_duplicates == reference["ignored_duplicates"]
    assert result.rating_eligible is reference["rating_eligible"]
    assert len(result.target_reports) == len(case["targets"])
    for target_id, expected in reference["per_target"].items():
        assert result.per_target[target_id] == pytest.approx(expected, abs=0.001)


def test_g5_production_node_uses_visibility_onset_not_scenario_start() -> None:
    case = CASES["G5"]
    result = score_proposed_golden_case_with_v1(
        "G5",
        DOCTRINE,
        case["targets"],
        case["events"],
        status=case["status"],
    )

    detection = result.target_reports[0].node_results[0]
    assert detection.action == "detect"
    assert detection.detection_delay_ms == 12_000


def test_g8_reaches_production_score_scenario_with_duplicate_v1_events() -> None:
    case = CASES["G8"]
    result = score_proposed_golden_case_with_v1(
        "G8",
        DOCTRINE,
        case["targets"],
        case["events"],
        status=case["status"],
    )

    report = result.target_reports[0]
    assert result.ignored_duplicates == 3
    assert report.total_score == pytest.approx(98.5, abs=0.01)
    assert len(report.node_results) == 3
    assert all(node.event_id is not None for node in report.node_results)
