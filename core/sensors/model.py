"""Deterministic abstract sensor visibility, noise, and dropout simulation.

This module is intentionally a training abstraction. Its values are not sensor
specifications and do not model real equipment or electronic-warfare behavior.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import hypot
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SensorConfig:
    """Editable abstract visibility parameters used only by the simulator."""

    base_visibility_radius_m: float = 650.0
    noise_std_m: float = 18.0
    dropout_probability: float = 0.08


@dataclass(frozen=True)
class SensorSample:
    """One deterministic abstract observation decision at a trajectory sample."""

    t_ms: int
    visible: bool
    range_m: float
    noisy_range_m: float
    dropped: bool


@dataclass(frozen=True)
class SensorTrace:
    """Sensor trace and the first fairly detectable playback timestamp."""

    target_id: str
    t_visible_ms: int | None
    samples: tuple[SensorSample, ...]


class SensorModel:
    """Apply abstract environment effects using a caller-owned NumPy generator."""

    def __init__(self, config: SensorConfig = SensorConfig()) -> None:
        if not 0 <= config.dropout_probability < 1:
            raise ValueError("dropout_probability must be in [0, 1)")
        if config.base_visibility_radius_m <= 0 or config.noise_std_m < 0:
            raise ValueError("sensor radii and noise must be non-negative")
        self._config = config

    def trace_target(
        self,
        target: Mapping[str, Any],
        environment: Mapping[str, str],
        rng: np.random.Generator,
    ) -> SensorTrace:
        """Return a repeatable visibility trace; no global RNG is used."""
        radius = self._config.base_visibility_radius_m * _environment_factor(environment)
        samples: list[SensorSample] = []
        t_visible_ms: int | None = None
        for point in target["trajectory"]:
            range_m = hypot(float(point["x_m"]), float(point["y_m"]))
            noisy_range_m = max(0.0, range_m + float(rng.normal(0.0, self._config.noise_std_m)))
            dropped = bool(rng.random() < self._config.dropout_probability)
            visible = not dropped and noisy_range_m <= radius
            sample = SensorSample(
                t_ms=int(point["t_ms"]),
                visible=visible,
                range_m=round(range_m, 3),
                noisy_range_m=round(noisy_range_m, 3),
                dropped=dropped,
            )
            samples.append(sample)
            if visible and t_visible_ms is None:
                t_visible_ms = sample.t_ms
        return SensorTrace(
            target_id=str(target["target_id"]),
            t_visible_ms=t_visible_ms,
            samples=tuple(samples),
        )


def _environment_factor(environment: Mapping[str, str]) -> float:
    """Return a deliberately simple, documented training-only visibility factor."""
    terrain = {"abstract_flat": 1.0, "rural": 0.92, "urban": 0.82}[environment["terrain"]]
    time_of_day = {"day": 1.0, "dawn_dusk": 0.82, "night": 0.68}[environment["time_of_day"]]
    weather = {"clear": 1.0, "haze": 0.78, "rain": 0.64}[environment["weather"]]
    return terrain * time_of_day * weather
