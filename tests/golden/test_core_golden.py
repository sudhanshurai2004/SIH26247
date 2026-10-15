"""Compatibility checks between core/scoring and the supplied proposed G1–G10 pack."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import reference_scorer as reference_scorer
import yaml

from core.scoring import (
    ProposedGoldenSpecError,
    load_proposed_golden_doctrine,
    score_proposed_golden_case,
    validate_proposed_golden_doctrine,
)

GOLDEN_DIR = Path(__file__).resolve().parent
DOCTRINE = load_proposed_golden_doctrine(GOLDEN_DIR / "doctrine_generic_demo_v1.yaml")
CASES: dict[str, dict[str, Any]] = yaml.safe_load(
    (GOLDEN_DIR / "golden_cases.yaml").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("golden_id", [f"G{index}" for index in range(1, 10)])
def test_core_proposed_golden_score_matches_reference(golden_id: str) -> None:
    case = CASES[golden_id]

    result = score_proposed_golden_case(
        DOCTRINE,
        case["targets"],
        case["events"],
        status=case["status"],
    ).as_dict()
    expected = case["expect"]
    reference = reference_scorer.score(
        DOCTRINE,
        case["targets"],
        case["events"],
        case["status"],
    )

    assert result["total"] == pytest.approx(reference["total"], abs=0.01)
    assert result["critical"] == reference["critical"]
    assert result["ignored_duplicates"] == reference["ignored_duplicates"]
    assert result["rating_eligible"] is reference["rating_eligible"]
    assert result["total"] == pytest.approx(expected["total"], abs=0.01)
    for target_id, target_score in expected["per_target"].items():
        assert result["per_target"][target_id] == pytest.approx(
            reference["per_target"][target_id], abs=0.001
        )
        assert result["per_target"][target_id] == pytest.approx(target_score, abs=0.001)


def test_g10_rejects_invalid_doctrine_without_replacing_valid_active_mapping() -> None:
    active_doctrine = copy.deepcopy(DOCTRINE)
    invalid_doctrine = copy.deepcopy(DOCTRINE)
    invalid_doctrine.update(CASES["G10"]["doctrine_override"])

    assert validate_proposed_golden_doctrine(invalid_doctrine) == ("weights_sum_invalid",)
    with pytest.raises(ProposedGoldenSpecError, match="weights_sum_invalid"):
        score_proposed_golden_case(
            invalid_doctrine,
            CASES["G1"]["targets"],
            CASES["G1"]["events"],
            status=CASES["G1"]["status"],
        )
    assert score_proposed_golden_case(
        active_doctrine,
        CASES["G1"]["targets"],
        CASES["G1"]["events"],
        status=CASES["G1"]["status"],
    ).total == pytest.approx(98.5, abs=0.01)
