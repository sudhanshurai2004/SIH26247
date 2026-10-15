"""Deterministic single-target scenario generation for Stage 2.

V0 deliberately models one abstract UAS trajectory. It precomputes every point
and a visibility onset marker so clients only play data; they do not simulate or
randomize the scenario themselves.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from math import cos, hypot, pi, sin
from typing import Any

import numpy as np

from core.generator.validation import ScenarioValidationError, validate_playback_scenario
from core.serialization import canonical_json, canonical_json_bytes

GENERATOR_VERSION = "0.1.0"
DEFAULT_DURATION_MS = 12_000
DEFAULT_TIME_STEP_MS = 1_000
MIN_ACTION_WINDOW_MS = 3_000


class ScenarioGenerationError(ScenarioValidationError):
    """Raised when a generated or supplied V0 scenario is not solvable."""


@dataclass(frozen=True)
class ScenarioProfile:
    """The contract-level profile inputs that affect a V0 scenario."""

    profile_id: str
    difficulty: int
    skill_tags: tuple[str, ...]

    def as_contract_payload(self) -> dict[str, Any]:
        """Return the exact JSON shape embedded in a scenario contract."""
        return {
            "profile_id": self.profile_id,
            "difficulty": self.difficulty,
            "skill_tags": list(self.skill_tags),
        }


def canonical_scenario_bytes(scenario: Mapping[str, Any]) -> bytes:
    """Validate then serialize a scenario in the stable replay representation."""
    validate_scenario(scenario)
    return canonical_json_bytes(scenario)


def generate_scenario(
    seed: int,
    profile: ScenarioProfile,
    *,
    version: str = GENERATOR_VERSION,
) -> dict[str, Any]:
    """Generate one valid, solvable V0 scenario from a local NumPy generator.

    The seed derivation incorporates the stated profile and generator version.
    It never uses Python's process-randomized ``hash`` or NumPy's global RNG.
    """
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ScenarioGenerationError("seed must be a non-negative integer")

    profile_payload = profile.as_contract_payload()
    rng = _rng_for(seed, profile_payload, version)
    duration_ms = DEFAULT_DURATION_MS
    time_step_ms = DEFAULT_TIME_STEP_MS

    # The path crosses an abstract observation area. The boundary is only a V0
    # visibility marker, not a real sensor specification; Stage 5 replaces it.
    start_range_m = int(rng.integers(1_000, 1_401))
    heading_rad = float(rng.uniform(-pi, pi))
    visibility_fraction = float(rng.uniform(0.25, 0.50))
    visibility_radius_m = start_range_m * visibility_fraction
    altitude_m = int(rng.integers(100, 241))

    start_x = start_range_m * cos(heading_rad)
    start_y = start_range_m * sin(heading_rad)
    trajectory = _linear_trajectory(
        start_x=start_x,
        start_y=start_y,
        altitude_m=altitude_m,
        duration_ms=duration_ms,
        time_step_ms=time_step_ms,
    )
    t_visible_ms = _first_visible_time(trajectory, visibility_radius_m)
    if t_visible_ms is None:
        raise ScenarioGenerationError("V0 trajectory did not enter the abstract visibility area")

    identity_material = canonical_json(
        {
            "generator_version": version,
            "profile": profile_payload,
            "seed": seed,
        }
    )
    scenario_id = f"scenario-{sha256(identity_material.encode('utf-8')).hexdigest()[:16]}"
    scenario: dict[str, Any] = {
        "contract_version": "1.0",
        "scenario_id": scenario_id,
        "generator_version": version,
        "seed": seed,
        "profile": profile_payload,
        "duration_ms": duration_ms,
        "time_step_ms": time_step_ms,
        "coordinate_system": "local_enu_m",
        "environment": {
            "terrain": "abstract_flat",
            "time_of_day": "day",
            "weather": "clear",
        },
        "targets": [
            {
                "target_id": "target-01",
                "entity_class": "uas",
                "affiliation": "simulated_threat",
                "t_visible_ms": t_visible_ms,
                "trajectory": trajectory,
            }
        ],
    }
    validate_scenario(scenario)
    return scenario


def validate_scenario(scenario: Mapping[str, Any]) -> None:
    """Check both the frozen contract and V0's single-target solvability rules."""
    try:
        validate_playback_scenario(scenario)
    except ScenarioValidationError as error:
        raise ScenarioGenerationError(str(error)) from error

    errors: list[str] = []
    targets = scenario["targets"]
    if len(targets) != 1:
        errors.append("V0 requires exactly one target")
    else:
        target = targets[0]
        if target["entity_class"] != "uas":
            errors.append("V0 target must use entity_class 'uas'")
        if target["affiliation"] != "simulated_threat":
            errors.append("V0 target must use affiliation 'simulated_threat'")
        if int(scenario["duration_ms"]) - int(target["t_visible_ms"]) < MIN_ACTION_WINDOW_MS:
            errors.append("target must remain actionable for the minimum decision window")

    if errors:
        raise ScenarioGenerationError("; ".join(errors))


def is_solvable(scenario: Mapping[str, Any]) -> bool:
    """Return whether a scenario passes all V0 structural/solvability checks."""
    try:
        validate_scenario(scenario)
    except ScenarioGenerationError:
        return False
    return True


def _rng_for(seed: int, profile: Mapping[str, Any], version: str) -> np.random.Generator:
    """Create a local PCG64 generator from stable JSON, never global state."""
    material = canonical_json({"seed": seed, "profile": profile, "version": version})
    entropy = int.from_bytes(sha256(material.encode("utf-8")).digest()[:16], "big")
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(entropy)))


def _linear_trajectory(
    *,
    start_x: float,
    start_y: float,
    altitude_m: int,
    duration_ms: int,
    time_step_ms: int,
) -> list[dict[str, float | int]]:
    """Precompute a linear path from one side of the abstract area to the other."""
    points: list[dict[str, float | int]] = []
    for t_ms in range(0, duration_ms + time_step_ms, time_step_ms):
        progress = t_ms / duration_ms
        points.append(
            {
                "t_ms": t_ms,
                "x_m": round(start_x * (1 - 2 * progress), 3),
                "y_m": round(start_y * (1 - 2 * progress), 3),
                "altitude_m": altitude_m,
            }
        )
    return points


def _first_visible_time(
    trajectory: list[dict[str, float | int]],
    visibility_radius_m: float,
) -> int | None:
    """Return the first precomputed point inside the V0 abstract visibility area."""
    for point in trajectory:
        if hypot(float(point["x_m"]), float(point["y_m"])) <= visibility_radius_m:
            return int(point["t_ms"])
    return None
