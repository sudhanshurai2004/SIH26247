"""Shared structural validation for generated playback scenarios."""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from core.contracts import ContractValidationError, validate_versioned_payload


class ScenarioValidationError(ValueError):
    """Raised when a contract-shaped scenario is unsafe or unsolvable to play."""


def validate_playback_scenario(scenario: Mapping[str, Any]) -> None:
    """Validate contract fields required by every generator version.

    The frozen JSON schema establishes shape. These checks establish replay
    invariants that JSON Schema cannot express: unique target IDs, monotonic
    regular timeline samples, finite coordinates, and a sampled visibility
    onset. Version-specific generators add their own solvability checks.
    """
    try:
        validate_versioned_payload("scenario", scenario)
    except ContractValidationError as error:
        raise ScenarioValidationError(str(error)) from error

    errors: list[str] = []
    target_ids = [target["target_id"] for target in scenario["targets"]]
    if len(target_ids) != len(set(target_ids)):
        errors.append("target_id values must be unique")

    duration_ms = int(scenario["duration_ms"])
    time_step_ms = int(scenario["time_step_ms"])
    for target in scenario["targets"]:
        trajectory = target["trajectory"]
        times = [int(point["t_ms"]) for point in trajectory]
        if times[0] != 0 or times[-1] != duration_ms:
            errors.append(f"target '{target['target_id']}' trajectory must cover the full duration")
        if any(later - earlier != time_step_ms for earlier, later in zip(times, times[1:])):
            errors.append(f"target '{target['target_id']}' timestamps must advance by time_step_ms")
        if int(target["t_visible_ms"]) not in times:
            errors.append(
                f"target '{target['target_id']}' t_visible_ms must be a trajectory timestamp"
            )
        if any(
            not isfinite(float(point[axis]))
            for point in trajectory
            for axis in ("x_m", "y_m", "altitude_m")
        ):
            errors.append(f"target '{target['target_id']}' coordinates must be finite")

    if errors:
        raise ScenarioValidationError("; ".join(errors))
