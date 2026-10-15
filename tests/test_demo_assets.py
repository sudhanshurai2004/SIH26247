"""Regression checks for the deliberately disposable five-minute demo kit."""

from __future__ import annotations

import json
from pathlib import Path

from core.generator import validate_playback_scenario

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "demo" / "scenarios"


def _load(filename: str) -> dict[str, object]:
    return json.loads((SCENARIOS / filename).read_text(encoding="utf-8"))


def test_three_ready_seeded_demo_scenarios_are_contract_valid() -> None:
    scripted = _load("01-scripted-clear-single.json")
    swarm = _load("02-swarm-rural-day.json")
    night = _load("03-night-degraded-urban.json")

    for scenario in (scripted, swarm, night):
        validate_playback_scenario(scenario)

    assert scripted["profile"]["profile_id"] == "demo-scripted-clear"
    assert swarm["environment"] == {"terrain": "rural", "time_of_day": "day", "weather": "clear"}
    assert len(swarm["targets"]) == 8  # six simulated threats and two abstract distractors
    assert night["environment"] == {"terrain": "urban", "time_of_day": "night", "weather": "rain"}
    assert night["profile"]["difficulty"] == 3
