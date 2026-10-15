"""Stage 2 deterministic single-target generator tests."""

from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from core.generator import (
    GENERATOR_VERSION,
    ScenarioGenerationError,
    ScenarioProfile,
    canonical_scenario_bytes,
    generate_scenario,
    is_solvable,
    validate_scenario,
)

PROFILE = ScenarioProfile(
    profile_id="intro-single-target",
    difficulty=1,
    skill_tags=("detection", "classification", "assessment", "response"),
)


def test_same_seed_profile_and_version_are_byte_identical_over_100_seeds() -> None:
    """This is the required deterministic regression sweep for generator V0."""
    scenario_ids: set[str] = set()
    for seed in range(100):
        first = generate_scenario(seed, PROFILE, version=GENERATOR_VERSION)
        second = generate_scenario(seed, PROFILE, version=GENERATOR_VERSION)

        assert canonical_scenario_bytes(first) == canonical_scenario_bytes(second)
        scenario_ids.add(first["scenario_id"])

    assert len(scenario_ids) == 100


def test_v0_precomputes_one_solvable_target_trajectory() -> None:
    scenario = generate_scenario(47, PROFILE)
    target = scenario["targets"][0]
    timestamps = [point["t_ms"] for point in target["trajectory"]]

    assert len(scenario["targets"]) == 1
    assert target["target_id"] == "target-01"
    assert timestamps[0] == 0
    assert timestamps[-1] == scenario["duration_ms"]
    assert target["t_visible_ms"] in timestamps
    assert scenario["duration_ms"] - target["t_visible_ms"] >= 3_000
    assert is_solvable(scenario)


def test_generator_does_not_mutate_numpy_global_random_state() -> None:
    np.random.seed(991)
    expected_after_generation = np.random.random(3)

    np.random.seed(991)
    generate_scenario(8, PROFILE)
    actual_after_generation = np.random.random(3)

    np.testing.assert_array_equal(actual_after_generation, expected_after_generation)


def test_profile_and_version_contribute_to_deterministic_identity() -> None:
    different_profile = ScenarioProfile(
        profile_id="advanced-single-target",
        difficulty=2,
        skill_tags=("detection", "classification"),
    )

    baseline = generate_scenario(9, PROFILE, version="0.1.0")
    changed_profile = generate_scenario(9, different_profile, version="0.1.0")
    changed_version = generate_scenario(9, PROFILE, version="0.1.1")

    assert baseline["scenario_id"] != changed_profile["scenario_id"]
    assert baseline["scenario_id"] != changed_version["scenario_id"]


def test_solvability_check_rejects_an_unactionable_visibility_marker() -> None:
    scenario = generate_scenario(1, PROFILE)
    invalid = deepcopy(scenario)
    invalid["targets"][0]["t_visible_ms"] = invalid["duration_ms"]

    with pytest.raises(ScenarioGenerationError, match="minimum decision window"):
        validate_scenario(invalid)


def test_generator_rejects_a_negative_seed() -> None:
    with pytest.raises(ScenarioGenerationError, match="non-negative"):
        generate_scenario(-1, PROFILE)
