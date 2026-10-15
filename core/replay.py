"""Deterministic interpolation of precomputed scenarios for replay clients."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.generator import validate_playback_scenario


@dataclass(frozen=True)
class ReplayTargetPosition:
    """One target's interpolated local-ENU position at a logical replay time."""

    target_id: str
    x_m: float
    y_m: float
    altitude_m: float


@dataclass(frozen=True)
class ReplayFrame:
    """A deterministic frame with no rendering or wall-clock dependency."""

    t_ms: int
    targets: tuple[ReplayTargetPosition, ...]


def replay_frame(scenario: Mapping[str, Any], t_ms: int) -> ReplayFrame:
    """Interpolate all target positions at a clamped logical playback offset."""
    validate_playback_scenario(scenario)
    clamped_time = max(0, min(int(t_ms), int(scenario["duration_ms"])))
    positions = tuple(_interpolate_target(target, clamped_time) for target in scenario["targets"])
    return ReplayFrame(t_ms=clamped_time, targets=positions)


def _interpolate_target(target: Mapping[str, Any], t_ms: int) -> ReplayTargetPosition:
    trajectory = target["trajectory"]
    for left, right in zip(trajectory, trajectory[1:]):
        if int(left["t_ms"]) <= t_ms <= int(right["t_ms"]):
            span = int(right["t_ms"]) - int(left["t_ms"])
            fraction = 0.0 if span == 0 else (t_ms - int(left["t_ms"])) / span
            return ReplayTargetPosition(
                target_id=str(target["target_id"]),
                x_m=round(
                    float(left["x_m"]) + (float(right["x_m"]) - float(left["x_m"])) * fraction, 3
                ),
                y_m=round(
                    float(left["y_m"]) + (float(right["y_m"]) - float(left["y_m"])) * fraction, 3
                ),
                altitude_m=round(
                    float(left["altitude_m"])
                    + (float(right["altitude_m"]) - float(left["altitude_m"])) * fraction,
                    3,
                ),
            )
    final = trajectory[-1]
    return ReplayTargetPosition(
        target_id=str(target["target_id"]),
        x_m=float(final["x_m"]),
        y_m=float(final["y_m"]),
        altitude_m=float(final["altitude_m"]),
    )
