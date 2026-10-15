"""Deterministic swarm/clutter scenario generation for the later MVP scope."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from math import cos, pi, sin
from typing import Any

import numpy as np

from core.generator.novelty import (
    DEFAULT_SEMANTIC_NOVELTY_POLICY,
    SemanticNoveltyPolicy,
    is_semantically_novel_scenario,
)
from core.generator.validation import ScenarioValidationError, validate_playback_scenario
from core.sensors import SensorConfig, SensorModel, SensorTrace
from core.serialization import canonical_json, canonical_json_bytes

GENERATOR_V1_VERSION = "1.0.0"
V1_DURATION_MS = 15_000
V1_TIME_STEP_MS = 1_000
V1_MIN_ACTION_WINDOW_MS = 3_000
CLUTTER_CLASSES = ("bird", "civil_uas", "friendly_aircraft", "balloon")


class ScenarioV1Error(ScenarioValidationError):
    """Raised when a V1 swarm or clutter scenario cannot be safely played."""


@dataclass(frozen=True)
class ScenarioV1Profile:
    """Inputs for generic, training-only swarms and clutter."""

    profile_id: str
    difficulty: int
    skill_tags: tuple[str, ...]
    swarm_size: int = 3
    clutter_count: int = 2
    terrain: str = "rural"
    time_of_day: str = "day"
    weather: str = "clear"

    def as_contract_payload(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "difficulty": self.difficulty,
            "skill_tags": list(self.skill_tags),
        }

    def environment(self) -> dict[str, str]:
        return {
            "terrain": self.terrain,
            "time_of_day": self.time_of_day,
            "weather": self.weather,
        }


@dataclass(frozen=True)
class ScenarioV1Bundle:
    """Scenario plus non-contract sensor traces useful for test/replay tooling."""

    scenario: dict[str, Any]
    sensor_traces: tuple[SensorTrace, ...]


def generate_scenario_v1(
    seed: int,
    profile: ScenarioV1Profile,
    *,
    version: str = GENERATOR_V1_VERSION,
    seen_fingerprints: Iterable[str] = (),
    recent_scenarios: Iterable[Mapping[str, Any]] = (),
    semantic_novelty_policy: SemanticNoveltyPolicy = DEFAULT_SEMANTIC_NOVELTY_POLICY,
) -> dict[str, Any]:
    """Generate a deterministic generic swarm/clutter scenario.

    Contract payloads remain limited to frozen V1-compatible fields. Sensor
    traces stay outside the payload; only their precomputed first-visible time
    is persisted on each target for deterministic scoring. ``recent_scenarios``
    is an ordered, caller-owned last-N window for the explicit local semantic
    novelty policy; no clock or global random state is read.
    """
    return generate_scenario_v1_bundle(
        seed,
        profile,
        version=version,
        seen_fingerprints=seen_fingerprints,
        recent_scenarios=recent_scenarios,
        semantic_novelty_policy=semantic_novelty_policy,
    ).scenario


def generate_scenario_v1_bundle(
    seed: int,
    profile: ScenarioV1Profile,
    *,
    version: str = GENERATOR_V1_VERSION,
    seen_fingerprints: Iterable[str] = (),
    recent_scenarios: Iterable[Mapping[str, Any]] = (),
    semantic_novelty_policy: SemanticNoveltyPolicy = DEFAULT_SEMANTIC_NOVELTY_POLICY,
) -> ScenarioV1Bundle:
    """Generate a V1 payload and its deterministic abstract sensor traces."""
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ScenarioV1Error("seed must be a non-negative integer")
    _validate_profile(profile)

    profile_payload = profile.as_contract_payload()
    environment = profile.environment()
    rng = _rng_for_v1(seed, profile_payload, environment, version)
    threat_trajectories = _boid_swarm_trajectories(profile.swarm_size, rng)
    clutter = _clutter_trajectories(profile.clutter_count, rng)
    raw_targets = [
        {
            "target_id": f"threat-{index + 1:02d}",
            "entity_class": "uas",
            "affiliation": "simulated_threat",
            "trajectory": trajectory,
        }
        for index, trajectory in enumerate(threat_trajectories)
    ]
    raw_targets.extend(clutter)

    sensor = SensorModel(SensorConfig())
    sensor_rng = _sensor_rng(seed, profile_payload, environment, version)
    traces = tuple(sensor.trace_target(target, environment, sensor_rng) for target in raw_targets)
    trace_by_target = {trace.target_id: trace for trace in traces}

    targets: list[dict[str, Any]] = []
    for target in raw_targets:
        trace = trace_by_target[target["target_id"]]
        fallback_time = min(trace.samples, key=lambda sample: sample.range_m).t_ms
        t_visible_ms = trace.t_visible_ms if trace.t_visible_ms is not None else fallback_time
        targets.append({**target, "t_visible_ms": t_visible_ms})

    identity_material = canonical_json(
        {
            "generator_version": version,
            "profile": profile_payload,
            "environment": environment,
            "seed": seed,
        }
    )
    scenario: dict[str, Any] = {
        "contract_version": "1.0",
        "scenario_id": f"scenario-v1-{sha256(identity_material.encode('utf-8')).hexdigest()[:16]}",
        "generator_version": version,
        "seed": seed,
        "profile": profile_payload,
        "duration_ms": V1_DURATION_MS,
        "time_step_ms": V1_TIME_STEP_MS,
        "coordinate_system": "local_enu_m",
        "environment": environment,
        "targets": targets,
    }
    validate_scenario_v1(scenario)
    fingerprint = scenario_fingerprint(scenario)
    if fingerprint in set(seen_fingerprints):
        raise ScenarioV1Error("scenario fails novelty check against supplied fingerprints")
    if not is_semantically_novel_scenario(
        scenario,
        recent_scenarios,
        policy=semantic_novelty_policy,
    ):
        raise ScenarioV1Error(
            "scenario fails semantic novelty check against supplied recent scenarios"
        )
    return ScenarioV1Bundle(scenario=scenario, sensor_traces=traces)


def validate_scenario_v1(scenario: Mapping[str, Any]) -> None:
    """Validate V1 swarm, clutter, and target-visibility constraints."""
    try:
        validate_playback_scenario(scenario)
    except ScenarioValidationError as error:
        raise ScenarioV1Error(str(error)) from error

    targets = scenario["targets"]
    threat_targets = [target for target in targets if target["affiliation"] == "simulated_threat"]
    errors: list[str] = []
    if len(targets) < 2:
        errors.append("V1 requires a swarm with at least two targets")
    if not threat_targets:
        errors.append("V1 requires at least one simulated threat target")
    for target in threat_targets:
        if target["entity_class"] != "uas":
            errors.append("simulated threat targets must use entity_class 'uas'")
        if V1_DURATION_MS - int(target["t_visible_ms"]) < V1_MIN_ACTION_WINDOW_MS:
            errors.append("simulated threat must retain the minimum decision window")
    if errors:
        raise ScenarioV1Error("; ".join(errors))


def canonical_scenario_v1_bytes(scenario: Mapping[str, Any]) -> bytes:
    """Return a validated, stable V1 scenario byte stream."""
    validate_scenario_v1(scenario)
    return canonical_json_bytes(scenario)


def scenario_fingerprint(scenario: Mapping[str, Any]) -> str:
    """Hash scenario content without the identity fields used to create it."""
    fingerprint_payload = {
        "profile": scenario["profile"],
        "environment": scenario["environment"],
        "targets": scenario["targets"],
    }
    return sha256(canonical_json(fingerprint_payload).encode("utf-8")).hexdigest()


def is_novel_scenario(scenario: Mapping[str, Any], seen_fingerprints: Iterable[str]) -> bool:
    """Return whether a generated scenario is absent from prior fingerprints."""
    return scenario_fingerprint(scenario) not in set(seen_fingerprints)


def _validate_profile(profile: ScenarioV1Profile) -> None:
    if not 2 <= profile.swarm_size <= 16:
        raise ScenarioV1Error("swarm_size must be between 2 and 16")
    if not 0 <= profile.clutter_count <= 16:
        raise ScenarioV1Error("clutter_count must be between 0 and 16")
    if profile.terrain not in {"abstract_flat", "rural", "urban"}:
        raise ScenarioV1Error("unsupported terrain")
    if profile.time_of_day not in {"day", "night", "dawn_dusk"}:
        raise ScenarioV1Error("unsupported time_of_day")
    if profile.weather not in {"clear", "haze", "rain"}:
        raise ScenarioV1Error("unsupported weather")


def _rng_for_v1(
    seed: int,
    profile: Mapping[str, Any],
    environment: Mapping[str, str],
    version: str,
) -> np.random.Generator:
    material = canonical_json(
        {"seed": seed, "profile": profile, "environment": environment, "version": version}
    )
    entropy = int.from_bytes(sha256(material.encode("utf-8")).digest()[:16], "big")
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(entropy)))


def _sensor_rng(
    seed: int,
    profile: Mapping[str, Any],
    environment: Mapping[str, str],
    version: str,
) -> np.random.Generator:
    material = canonical_json(
        {
            "seed": seed,
            "profile": profile,
            "environment": environment,
            "version": version,
            "stream": "sensor",
        }
    )
    entropy = int.from_bytes(sha256(material.encode("utf-8")).digest()[:16], "big")
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(entropy)))


def _boid_swarm_trajectories(
    swarm_size: int,
    rng: np.random.Generator,
) -> list[list[dict[str, float | int]]]:
    """Precompute a small cohesion/alignment/separation swarm around an anchor."""
    point_count = V1_DURATION_MS // V1_TIME_STEP_MS + 1
    heading = float(rng.uniform(-pi, pi))
    start_radius = float(rng.integers(1_000, 1_301))
    anchor_start = np.array([start_radius * cos(heading), start_radius * sin(heading)])
    offsets = rng.normal(0.0, 70.0, size=(swarm_size, 2))
    velocities = rng.normal(0.0, 8.0, size=(swarm_size, 2))
    altitudes = rng.integers(110, 221, size=swarm_size)
    trajectories: list[list[dict[str, float | int]]] = [[] for _ in range(swarm_size)]

    for step in range(point_count):
        t_ms = step * V1_TIME_STEP_MS
        progress = step / (point_count - 1)
        anchor = anchor_start * (1 - 2 * progress)
        for index in range(swarm_size):
            position = anchor + offsets[index]
            trajectories[index].append(
                {
                    "t_ms": t_ms,
                    "x_m": round(float(position[0]), 3),
                    "y_m": round(float(position[1]), 3),
                    "altitude_m": int(altitudes[index]),
                }
            )

        if step == point_count - 1:
            continue
        centroid = offsets.mean(axis=0)
        mean_velocity = velocities.mean(axis=0)
        separation = np.zeros_like(offsets)
        for left in range(swarm_size):
            for right in range(left + 1, swarm_size):
                delta = offsets[left] - offsets[right]
                distance = float(np.linalg.norm(delta))
                if 0 < distance < 85:
                    adjustment = (delta / distance) * (85 - distance) * 0.12
                    separation[left] += adjustment
                    separation[right] -= adjustment
        # These are abstract boid terms, not real flight or threat behavior.
        velocities = (
            0.55 * velocities + 0.25 * mean_velocity - 0.15 * (offsets - centroid) + separation
        )
        offsets = offsets + velocities

    return trajectories


def _clutter_trajectories(
    clutter_count: int,
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    """Create generic bird/civil/friendly/balloon distractor trajectories."""
    targets: list[dict[str, Any]] = []
    for index in range(clutter_count):
        entity_class = str(rng.choice(CLUTTER_CLASSES))
        affiliation = "friendly" if entity_class == "friendly_aircraft" else "non_hostile"
        heading = float(rng.uniform(-pi, pi))
        start_radius = float(rng.integers(800, 1_501))
        start_x = start_radius * cos(heading)
        start_y = start_radius * sin(heading)
        altitude = int(rng.integers(60, 281))
        trajectory = []
        for t_ms in range(0, V1_DURATION_MS + V1_TIME_STEP_MS, V1_TIME_STEP_MS):
            progress = t_ms / V1_DURATION_MS
            lateral = (progress - 0.5) * float(rng.uniform(-35.0, 35.0))
            trajectory.append(
                {
                    "t_ms": t_ms,
                    "x_m": round(start_x * (1 - 1.6 * progress) + lateral, 3),
                    "y_m": round(start_y * (1 - 1.6 * progress) - lateral, 3),
                    "altitude_m": altitude,
                }
            )
        targets.append(
            {
                "target_id": f"clutter-{index + 1:02d}",
                "entity_class": entity_class,
                "affiliation": affiliation,
                "trajectory": trajectory,
            }
        )
    return targets
