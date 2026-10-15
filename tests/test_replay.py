"""Deterministic replay interpolation tests."""

from __future__ import annotations

from core.generator import ScenarioProfile, generate_scenario
from core.replay import replay_frame


def test_replay_interpolates_precomputed_trajectory_at_logical_time() -> None:
    scenario = generate_scenario(
        2,
        ScenarioProfile("replay-target", 1, ("detection",)),
    )
    target = scenario["targets"][0]
    first = target["trajectory"][0]
    second = target["trajectory"][1]

    frame = replay_frame(scenario, 500)
    position = frame.targets[0]

    assert position.x_m == round((first["x_m"] + second["x_m"]) / 2, 3)
    assert position.y_m == round((first["y_m"] + second["y_m"]) / 2, 3)


def test_replay_clamps_to_scenario_duration() -> None:
    scenario = generate_scenario(
        3,
        ScenarioProfile("replay-clamp", 1, ("detection",)),
    )

    frame = replay_frame(scenario, 999_999)

    assert frame.t_ms == scenario["duration_ms"]
