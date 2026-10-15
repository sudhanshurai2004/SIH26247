"""Generator V1 swarm, clutter, novelty, and sensor-model tests."""

from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from core.generator import (
    ScenarioV1Error,
    ScenarioV1Profile,
    canonical_scenario_v1_bytes,
    generate_scenario_v1,
    is_semantically_novel_scenario,
    scenario_fingerprint,
    scenario_semantic_signature,
    semantic_similarity,
    validate_scenario_v1,
)
from core.sensors import SensorModel

PROFILE = ScenarioV1Profile(
    profile_id="v1-swarm",
    difficulty=3,
    skill_tags=("detection", "classification"),
    swarm_size=4,
    clutter_count=6,
    terrain="urban",
    time_of_day="dawn_dusk",
    weather="haze",
)


def test_v1_scenario_is_byte_identical_and_contains_swarm_and_clutter() -> None:
    first = generate_scenario_v1(103, PROFILE)
    second = generate_scenario_v1(103, PROFILE)

    assert canonical_scenario_v1_bytes(first) == canonical_scenario_v1_bytes(second)
    assert len(first["targets"]) == PROFILE.swarm_size + PROFILE.clutter_count
    assert sum(target["affiliation"] == "simulated_threat" for target in first["targets"]) == 4
    assert {target["entity_class"] for target in first["targets"]}.issubset(
        {"uas", "bird", "civil_uas", "friendly_aircraft", "balloon"}
    )
    validate_scenario_v1(first)


def test_v1_sensor_trace_is_seeded_and_has_dropout_data() -> None:
    scenario = generate_scenario_v1(77, PROFILE)
    target = scenario["targets"][0]
    environment = scenario["environment"]
    first_rng = np.random.Generator(np.random.PCG64(88))
    second_rng = np.random.Generator(np.random.PCG64(88))

    first_trace = SensorModel().trace_target(target, environment, first_rng)
    second_trace = SensorModel().trace_target(target, environment, second_rng)

    assert first_trace == second_trace
    assert len(first_trace.samples) == len(target["trajectory"])
    assert all(isinstance(sample.dropped, bool) for sample in first_trace.samples)


def test_v1_novelty_check_rejects_an_existing_fingerprint() -> None:
    scenario = generate_scenario_v1(19, PROFILE)

    with pytest.raises(ScenarioV1Error, match="novelty"):
        generate_scenario_v1(19, PROFILE, seen_fingerprints=[scenario_fingerprint(scenario)])


def test_v1_semantic_novelty_rejects_a_near_duplicate_but_allows_a_distinct_seed() -> None:
    scenario = generate_scenario_v1(19, PROFILE)
    near_duplicate = deepcopy(scenario)
    near_duplicate["scenario_id"] = "scenario-v1-semantic-near-duplicate"
    near_duplicate["targets"][0]["trajectory"][1]["x_m"] += 0.001
    validate_scenario_v1(near_duplicate)

    assert scenario_fingerprint(near_duplicate) != scenario_fingerprint(scenario)
    assert scenario_semantic_signature(near_duplicate) == scenario_semantic_signature(scenario)
    assert semantic_similarity(near_duplicate, scenario) == 1.0
    assert not is_semantically_novel_scenario(near_duplicate, [scenario])
    with pytest.raises(ScenarioV1Error, match="semantic novelty"):
        generate_scenario_v1(19, PROFILE, recent_scenarios=[scenario])

    distinct = generate_scenario_v1(20, PROFILE)
    assert is_semantically_novel_scenario(distinct, [scenario])


def test_v1_does_not_mutate_numpy_global_rng_state() -> None:
    np.random.seed(444)
    expected = np.random.random(2)

    np.random.seed(444)
    generate_scenario_v1(44, PROFILE)
    actual = np.random.random(2)

    np.testing.assert_array_equal(actual, expected)
