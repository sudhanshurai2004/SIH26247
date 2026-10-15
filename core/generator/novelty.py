"""Deterministic semantic novelty checks for generated V1 training scenarios.

The Execution Blueprint calls for a feature signature and comparison against a
trainee's last N scenarios, but does not define a signature, metric, N, or
threshold.  This module therefore makes the local policy explicit and keeps it
small, deterministic, and independently testable.  It does not claim that its
metric was prescribed by the Blueprint.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import atan2, hypot
from typing import Any

from core.generator.validation import ScenarioValidationError, validate_playback_scenario


@dataclass(frozen=True)
class SemanticNoveltyPolicy:
    """Local, explicit window and Jaccard threshold for semantic repeat checks."""

    recent_session_count: int = 5
    maximum_similarity: float = 0.85

    def __post_init__(self) -> None:
        if not isinstance(self.recent_session_count, int) or isinstance(
            self.recent_session_count, bool
        ):
            raise ValueError("recent_session_count must be an integer")
        if self.recent_session_count < 1:
            raise ValueError("recent_session_count must be at least one")
        if not 0.0 <= self.maximum_similarity <= 1.0:
            raise ValueError("maximum_similarity must be between zero and one")


DEFAULT_SEMANTIC_NOVELTY_POLICY = SemanticNoveltyPolicy()


def scenario_semantic_signature(scenario: Mapping[str, Any]) -> frozenset[str]:
    """Return an order/ID-free set of coarse, training-relevant feature tokens.

    Target IDs, scenario IDs, seed, and raw point coordinates deliberately do
    not affect the signature.  The signature instead records mission profile,
    environment, target composition, visibility-band composition, and coarse
    radial motion/heading composition.  This allows a genuinely different
    generated scenario to pass while preventing a clone or a tiny-coordinate
    edit from evading novelty checks.
    """
    try:
        validate_playback_scenario(scenario)
    except ScenarioValidationError as error:
        raise ValueError(str(error)) from error

    profile = scenario["profile"]
    environment = scenario["environment"]
    targets = scenario["targets"]
    duration_ms = int(scenario["duration_ms"])
    tokens = {
        f"difficulty:{profile['difficulty']}",
        f"terrain:{environment['terrain']}",
        f"time_of_day:{environment['time_of_day']}",
        f"weather:{environment['weather']}",
        f"target_count:{len(targets)}",
    }
    tokens.update(f"skill:{skill_tag}" for skill_tag in sorted(profile["skill_tags"]))

    class_counts = Counter(
        f"{target['affiliation']}:{target['entity_class']}" for target in targets
    )
    tokens.update(f"class_count:{key}:{value}" for key, value in sorted(class_counts.items()))

    visible_counts = Counter(
        _visibility_band(int(target["t_visible_ms"]), duration_ms) for target in targets
    )
    tokens.update(f"visible:{band}:{count}" for band, count in sorted(visible_counts.items()))

    motion_counts = Counter(_motion_band(target) for target in targets)
    tokens.update(f"motion:{band}:{count}" for band, count in sorted(motion_counts.items()))
    return frozenset(tokens)


def semantic_similarity(
    first: Mapping[str, Any] | frozenset[str], second: Mapping[str, Any] | frozenset[str]
) -> float:
    """Return Jaccard similarity of two deterministic semantic signatures."""
    first_signature = first if isinstance(first, frozenset) else scenario_semantic_signature(first)
    second_signature = (
        second if isinstance(second, frozenset) else scenario_semantic_signature(second)
    )
    union = first_signature | second_signature
    if not union:
        return 1.0
    return len(first_signature & second_signature) / len(union)


def is_semantically_novel_scenario(
    scenario: Mapping[str, Any],
    recent_scenarios: Iterable[Mapping[str, Any]],
    *,
    policy: SemanticNoveltyPolicy = DEFAULT_SEMANTIC_NOVELTY_POLICY,
) -> bool:
    """Return false if any supplied recent scenario reaches the local threshold."""
    candidate = scenario_semantic_signature(scenario)
    return all(
        semantic_similarity(candidate, scenario_semantic_signature(prior))
        < policy.maximum_similarity
        for prior in recent_scenarios
    )


def most_similar_recent_scenario(
    scenario: Mapping[str, Any],
    recent_scenarios: Iterable[Mapping[str, Any]],
) -> float | None:
    """Return the highest comparison score, or ``None`` when history is empty."""
    candidate = scenario_semantic_signature(scenario)
    scores = [
        semantic_similarity(candidate, scenario_semantic_signature(prior))
        for prior in recent_scenarios
    ]
    return max(scores) if scores else None


def _visibility_band(t_visible_ms: int, duration_ms: int) -> str:
    ratio = t_visible_ms / duration_ms
    if ratio < 0.25:
        return "early"
    if ratio < 0.5:
        return "mid"
    if ratio < 0.75:
        return "late"
    return "very_late"


def _motion_band(target: Mapping[str, Any]) -> str:
    """Reduce a trajectory to radial change plus one of eight heading sectors."""
    trajectory = target["trajectory"]
    start = trajectory[0]
    end = trajectory[-1]
    start_range = hypot(float(start["x_m"]), float(start["y_m"]))
    end_range = hypot(float(end["x_m"]), float(end["y_m"]))
    range_change = end_range - start_range
    if range_change < -75:
        radial = "approaching"
    elif range_change > 75:
        radial = "departing"
    else:
        radial = "lateral"

    heading = atan2(
        float(end["y_m"]) - float(start["y_m"]), float(end["x_m"]) - float(start["x_m"])
    )
    sector = int(((heading + 3.141592653589793) / (2 * 3.141592653589793)) * 8) % 8
    return f"{target['affiliation']}:{radial}:heading_{sector}"
