"""Compatibility evaluator for the user-supplied proposed G1–G10 pack.

The pack is deliberately kept separate from the frozen ``1.0`` scenario,
event, and doctrine contracts.  Its lightweight YAML fields and uppercase event
names are not contract-v1 payloads, so changing the production schemas merely
to accept test material would break the frozen-contract boundary.  This module
implements the proposed pack verbatim and is intentionally restricted to its
abstract, training-only vocabulary.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ProposedGoldenSpecError(ValueError):
    """Raised when a proposed G1–G10 doctrine or case is malformed."""


@dataclass(frozen=True)
class ProposedGoldenScore:
    """Result shape intentionally aligned with the supplied reference scorer."""

    per_target: dict[str, float]
    critical: tuple[str, ...]
    total: float
    ignored_duplicates: int
    rating_eligible: bool

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-safe keys matching the supplied reference scorer."""
        return {
            "per_target": self.per_target,
            "critical": list(self.critical),
            "total": self.total,
            "ignored_duplicates": self.ignored_duplicates,
            "rating_eligible": self.rating_eligible,
        }


def load_proposed_golden_doctrine(path: Path) -> dict[str, Any]:
    """Safely load the proposed, explicitly non-production golden doctrine."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ProposedGoldenSpecError(
            "proposed golden doctrine could not be loaded safely"
        ) from error
    if not isinstance(document, dict):
        raise ProposedGoldenSpecError("proposed golden doctrine root must be an object")
    errors = validate_proposed_golden_doctrine(document)
    if errors:
        raise ProposedGoldenSpecError("; ".join(errors))
    return document


def validate_proposed_golden_doctrine(doctrine: Mapping[str, Any]) -> tuple[str, ...]:
    """Validate the supplied pack's narrow doctrine format without YAML execution.

    ``weights_sum_invalid`` is retained exactly because G10 asserts that token.
    Other messages make malformed hand-authored test data diagnosable without
    asserting a different production doctrine contract.
    """
    errors: list[str] = []
    classes = doctrine.get("classes")
    weights = doctrine.get("weights")
    if not isinstance(classes, list) or not all(isinstance(item, str) for item in classes):
        errors.append("classes_invalid")
    if not isinstance(weights, Mapping) or set(weights) != {
        "detect",
        "classify",
        "respond",
        "time",
    }:
        errors.append("weights_invalid")
    else:
        try:
            weight_total = sum(float(value) for value in weights.values())
        except (TypeError, ValueError):
            errors.append("weights_invalid")
        else:
            if abs(weight_total - 1.0) > 1e-9:
                errors.append("weights_sum_invalid")
    for required in (
        "dt_max_s",
        "critical_penalty_points",
        "cap_on_engage_friendly",
        "engagement_actions",
        "partial_credit",
        "response_matrix",
    ):
        if required not in doctrine:
            errors.append(f"missing:{required}")

    response_matrix = doctrine.get("response_matrix")
    if isinstance(response_matrix, Mapping) and isinstance(classes, list):
        for classification, zones in response_matrix.items():
            if classification not in classes:
                errors.append(f"unknown_class:{classification}")
            if not isinstance(zones, Mapping):
                errors.append(f"response_matrix_invalid:{classification}")
                continue
            for zone in ("outer", "inner"):
                response = zones.get(zone)
                has_expected_lists = (
                    isinstance(response, Mapping)
                    and isinstance(response.get("best"), list)
                    and isinstance(response.get("acceptable"), list)
                )
                if not has_expected_lists:
                    errors.append(f"response_matrix_invalid:{classification}:{zone}")
    elif response_matrix is not None:
        errors.append("response_matrix_invalid")
    return tuple(errors)


def score_proposed_golden_case(
    doctrine: Mapping[str, Any],
    targets: Iterable[Mapping[str, Any]],
    events: Iterable[Mapping[str, Any]],
    status: str = "completed",
) -> ProposedGoldenScore:
    """Score a G1–G10 case exactly as the supplied reference scorer specifies.

    Event IDs are deduplicated before scoring, detection delay starts at each
    target's ``t_visible_ms``, and interrupted attempts remain scored but are
    excluded from rating eligibility.  This evaluator has no production
    session/database effects; production event conflict handling stays stricter
    for non-identical duplicate IDs.
    """
    errors = validate_proposed_golden_doctrine(doctrine)
    if errors:
        raise ProposedGoldenSpecError("; ".join(errors))
    target_list = [dict(target) for target in targets]
    if not target_list:
        raise ProposedGoldenSpecError("at least one proposed golden target is required")
    if status not in {"completed", "interrupted"}:
        raise ProposedGoldenSpecError("status must be 'completed' or 'interrupted'")

    unique_events, ignored_duplicates = _deduplicate_events(events)
    weights = doctrine["weights"]
    per_target: dict[str, float] = {}
    critical: list[str] = []
    friendly_cap = False

    for target in target_list:
        _validate_target(target)
        target_id = str(target["id"])
        target_events = sorted(
            (event for event in unique_events if event["target"] == target_id),
            key=lambda event: int(event["t_ms"]),
        )
        detect = next((event for event in target_events if event["type"] == "DETECT"), None)
        classify = next(
            (
                event
                for event in target_events
                if event["type"] == "CLASSIFY"
                and detect is not None
                and int(event["t_ms"]) >= int(detect["t_ms"])
            ),
            None,
        )
        respond = next((event for event in target_events if event["type"] == "RESPOND"), None)

        detection_credit = 1.0 if detect is not None else 0.0
        timing_credit = _timing_credit(detect, target, float(doctrine["dt_max_s"]))
        classification_credit = _classification_credit(doctrine, target, classify)
        response_credit = _response_credit(doctrine, target, detect, respond)
        score = (
            float(weights["detect"]) * detection_credit
            + float(weights["classify"]) * classification_credit
            + float(weights["respond"]) * response_credit
            + float(weights["time"]) * timing_credit
        )
        per_target[target_id] = round(score, 4)

        target_class = str(target["true_class"])
        if (
            respond is not None
            and respond.get("value") in doctrine["engagement_actions"]
            and target_class != "hostile_small_uas"
        ):
            critical.append(f"engage_nonhostile:{target_id}")
            if target_class == "friendly_aircraft":
                friendly_cap = True
        if (
            status == "completed"
            and target_class == "hostile_small_uas"
            and bool(target.get("reaches_inner"))
            and respond is None
        ):
            critical.append(f"miss_hostile_at_inner_zone:{target_id}")

    raw_total = 100.0 * sum(per_target.values()) / len(target_list)
    total = max(0.0, raw_total - float(doctrine["critical_penalty_points"]) * len(critical))
    if friendly_cap:
        total = min(total, float(doctrine["cap_on_engage_friendly"]))
    return ProposedGoldenScore(
        per_target=per_target,
        critical=tuple(critical),
        total=round(total, 2),
        ignored_duplicates=ignored_duplicates,
        rating_eligible=status == "completed",
    )


def _deduplicate_events(events: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Apply G8's first-event-wins semantics by event ID."""
    seen: set[str] = set()
    unique_events: list[dict[str, Any]] = []
    duplicates = 0
    for supplied_event in events:
        event = dict(supplied_event)
        _validate_event(event)
        event_id = str(event["id"])
        if event_id in seen:
            duplicates += 1
            continue
        seen.add(event_id)
        unique_events.append(event)
    return unique_events, duplicates


def _validate_target(target: Mapping[str, Any]) -> None:
    required = {"id", "true_class", "t_visible_ms", "response_zone"}
    if not required.issubset(target):
        raise ProposedGoldenSpecError("golden target is missing required fields")
    if target["response_zone"] not in {"outer", "inner"}:
        raise ProposedGoldenSpecError("golden target response_zone must be 'outer' or 'inner'")
    try:
        if int(target["t_visible_ms"]) < 0:
            raise ValueError
    except (TypeError, ValueError) as error:
        raise ProposedGoldenSpecError("golden target t_visible_ms must be non-negative") from error


def _validate_event(event: Mapping[str, Any]) -> None:
    required = {"id", "t_ms", "type", "target"}
    if not required.issubset(event):
        raise ProposedGoldenSpecError("golden event is missing required fields")
    if event["type"] not in {"DETECT", "CLASSIFY", "RESPOND"}:
        raise ProposedGoldenSpecError("golden event type is unsupported")
    try:
        if int(event["t_ms"]) < 0:
            raise ValueError
    except (TypeError, ValueError) as error:
        raise ProposedGoldenSpecError("golden event t_ms must be non-negative") from error
    if event["type"] in {"CLASSIFY", "RESPOND"} and "value" not in event:
        raise ProposedGoldenSpecError("golden classify/respond event requires value")


def _timing_credit(
    detect: Mapping[str, Any] | None,
    target: Mapping[str, Any],
    dt_max_s: float,
) -> float:
    if detect is None:
        return 0.0
    if dt_max_s <= 0:
        raise ProposedGoldenSpecError("dt_max_s must be positive")
    delay_seconds = max(0.0, (int(detect["t_ms"]) - int(target["t_visible_ms"])) / 1000.0)
    return max(0.0, 1.0 - delay_seconds / dt_max_s)


def _classification_credit(
    doctrine: Mapping[str, Any],
    target: Mapping[str, Any],
    classify: Mapping[str, Any] | None,
) -> float:
    if classify is None:
        return 0.0
    target_class = str(target["true_class"])
    supplied_value = classify["value"]
    if supplied_value == target_class:
        return 1.0
    partial_credit = doctrine["partial_credit"]
    allowed_partial = (
        partial_credit.get(target_class, []) if isinstance(partial_credit, Mapping) else []
    )
    return 0.5 if supplied_value in allowed_partial else 0.0


def _response_credit(
    doctrine: Mapping[str, Any],
    target: Mapping[str, Any],
    detect: Mapping[str, Any] | None,
    respond: Mapping[str, Any] | None,
) -> float:
    if detect is None or respond is None:
        return 0.0
    response_matrix = doctrine["response_matrix"]
    target_class = str(target["true_class"])
    if target_class not in response_matrix:
        return 0.0
    expected = response_matrix[target_class][target["response_zone"]]
    if respond["value"] in expected["best"]:
        return 1.0
    return 0.5 if respond["value"] in expected["acceptable"] else 0.0
