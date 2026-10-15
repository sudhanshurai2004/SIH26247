"""Bridge the proposed G1–G10 pack through the frozen production v1 scorer.

The user-supplied golden pack deliberately has a compact, non-v1 YAML shape.
This adapter converts its targets, events, and placeholder doctrine into valid
contract-v1 inputs, then delegates each target's decision-tree score to
:func:`core.scoring.engine.score_scenario`.  Aggregate critical-error policy is
kept in this explicit sidecar because contract v1 has no fields for protected
zones, friendly caps, or class-specific response matrices.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import ceil
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from core.scoring.engine import ScoreReport, score_scenario
from core.scoring.proposed_golden import ProposedGoldenSpecError, validate_proposed_golden_doctrine

_CLASSIFICATION_MAP = {
    "hostile_small_uas": "simulated_threat",
    "civil_uas": "civil_uas",
    "bird": "bird",
    "friendly_aircraft": "friendly_aircraft",
    "clutter": "other",
}
_ENTITY_MAP = {
    "hostile_small_uas": ("uas", "simulated_threat"),
    "civil_uas": ("civil_uas", "non_hostile"),
    "bird": ("bird", "non_hostile"),
    "friendly_aircraft": ("friendly_aircraft", "friendly"),
    "clutter": ("balloon", "unknown"),
}
_RESPONSE_MAP = {
    "alert_and_track": "report",
    "observe": "monitor",
    "soft_response": "escalate",
    "hard_response": "defer",
    "observe_and_report": "report",
    "warn": "report",
    "hold_fire": "monitor",
}
_ALLOWED_RESPONSES = ("monitor", "report", "escalate", "defer")
# 0.35 * (1 - delay / 46.667s) reproduces
# 0.20 + 0.15 * (1 - delay / 20s), within the pack's 0.01 tolerance.
_TIMING_LATE_MS = 46_667


@dataclass(frozen=True)
class GoldenV1AdapterReport:
    """Aggregate proposed-pack result plus evidence from real v1 scoring calls."""

    per_target: dict[str, float]
    critical: tuple[str, ...]
    total: float
    ignored_duplicates: int
    rating_eligible: bool
    target_reports: tuple[ScoreReport, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return reference-compatible aggregate fields for golden assertions."""
        return {
            "per_target": self.per_target,
            "critical": list(self.critical),
            "total": self.total,
            "ignored_duplicates": self.ignored_duplicates,
            "rating_eligible": self.rating_eligible,
        }


def score_proposed_golden_case_with_v1(
    golden_id: str,
    proposed_doctrine: Mapping[str, Any],
    targets: Iterable[Mapping[str, Any]],
    events: Iterable[Mapping[str, Any]],
    status: str = "completed",
) -> GoldenV1AdapterReport:
    """Run a proposed G1–G10 case through valid v1 payloads and ``score_scenario``.

    This is intentionally an adapter, not a replacement for production doctrine
    semantics.  It proves that the frozen core scorer handles the translated
    detection, classification, response, interruption, and retry paths while
    preserving explicit sidecar policy for data fields that v1 cannot encode.
    """
    doctrine_errors = validate_proposed_golden_doctrine(proposed_doctrine)
    if doctrine_errors:
        raise ProposedGoldenSpecError("; ".join(doctrine_errors))
    if status not in {"completed", "interrupted"}:
        raise ProposedGoldenSpecError("status must be 'completed' or 'interrupted'")

    target_list = [dict(target) for target in targets]
    if not target_list:
        raise ProposedGoldenSpecError("at least one golden target is required")
    source_event_list = [dict(event) for event in events]
    unique_events, ignored_duplicates = _deduplicate_source_events(source_event_list)
    target_reports: list[ScoreReport] = []
    per_target: dict[str, float] = {}
    critical: list[str] = []
    friendly_cap = False

    for target in target_list:
        _validate_target(target)
        target_id = str(target["id"])
        target_events = [event for event in source_event_list if event["target"] == target_id]
        unique_target_events = [event for event in unique_events if event["target"] == target_id]
        scenario, v1_events, doctrine = _to_v1_payloads(
            golden_id=golden_id,
            proposed_doctrine=proposed_doctrine,
            target=target,
            source_events=target_events,
        )
        report = score_scenario(
            scenario,
            v1_events,
            doctrine,
            interrupted=status == "interrupted",
        )
        target_reports.append(report)
        per_target[target_id] = round(report.total_score / report.max_score, 4)

        response = _first_response(unique_target_events)
        target_class = str(target["true_class"])
        if (
            response is not None
            and response.get("value") in proposed_doctrine["engagement_actions"]
            and target_class != "hostile_small_uas"
        ):
            critical.append(f"engage_nonhostile:{target_id}")
            if target_class == "friendly_aircraft":
                friendly_cap = True
        if (
            status == "completed"
            and target_class == "hostile_small_uas"
            and bool(target.get("reaches_inner"))
            and response is None
        ):
            critical.append(f"miss_hostile_at_inner_zone:{target_id}")

    raw_total = 100.0 * sum(per_target.values()) / len(target_list)
    total = max(
        0.0, raw_total - float(proposed_doctrine["critical_penalty_points"]) * len(critical)
    )
    if friendly_cap:
        total = min(total, float(proposed_doctrine["cap_on_engage_friendly"]))
    return GoldenV1AdapterReport(
        per_target=per_target,
        critical=tuple(critical),
        total=round(total, 2),
        ignored_duplicates=ignored_duplicates,
        rating_eligible=status == "completed",
        target_reports=tuple(target_reports),
    )


def _to_v1_payloads(
    *,
    golden_id: str,
    proposed_doctrine: Mapping[str, Any],
    target: Mapping[str, Any],
    source_events: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    target_id = str(target["id"])
    v1_target_id = f"target-{target_id}"
    target_class = str(target["true_class"])
    if target_class not in _ENTITY_MAP or target_class not in _CLASSIFICATION_MAP:
        raise ProposedGoldenSpecError(f"unsupported golden target class: {target_class}")
    if target_class not in proposed_doctrine["response_matrix"]:
        raise ProposedGoldenSpecError(f"golden doctrine has no response matrix for {target_class}")
    response_zone = str(target["response_zone"])
    response_rule = proposed_doctrine["response_matrix"][target_class].get(response_zone)
    if not isinstance(response_rule, Mapping):
        raise ProposedGoldenSpecError(f"invalid response zone for {target_id}")

    max_time = max(
        [int(target["t_visible_ms"]), *(int(event["t_ms"]) for event in source_events)],
        default=int(target["t_visible_ms"]),
    )
    duration_ms = max(1_000, ceil((max_time + 1_000) / 1_000) * 1_000)
    entity_class, affiliation = _ENTITY_MAP[target_class]
    scenario_id = f"golden-{golden_id}-{target_id}"
    scenario = {
        "contract_version": "1.0",
        "scenario_id": scenario_id,
        "generator_version": "1.0.0",
        "seed": _stable_seed(golden_id, target_id),
        "profile": {
            "profile_id": "golden-v1-adapter",
            "difficulty": 1,
            "skill_tags": ["detection", "classification", "response"],
        },
        "duration_ms": duration_ms,
        "time_step_ms": 1_000,
        "coordinate_system": "local_enu_m",
        "environment": {"terrain": "abstract_flat", "time_of_day": "day", "weather": "clear"},
        "targets": [
            {
                "target_id": v1_target_id,
                "entity_class": entity_class,
                "affiliation": affiliation,
                "t_visible_ms": int(target["t_visible_ms"]),
                "trajectory": [
                    {
                        "t_ms": time_ms,
                        "x_m": 100.0,
                        "y_m": 0.0,
                        "altitude_m": 100.0,
                    }
                    for time_ms in range(0, duration_ms + 1_000, 1_000)
                ],
            }
        ],
    }
    doctrine = _v1_doctrine(
        golden_id=golden_id,
        target_class=target_class,
        response_rule=response_rule,
    )
    converted_events = _v1_events(
        golden_id=golden_id,
        scenario_id=scenario_id,
        target_id=v1_target_id,
        source_events=source_events,
    )
    return scenario, converted_events, doctrine


def _v1_doctrine(
    *,
    golden_id: str,
    target_class: str,
    response_rule: Mapping[str, Any],
) -> dict[str, Any]:
    best_responses = [_map_response(value) for value in response_rule["best"]]
    return {
        "contract_version": "1.0",
        "doctrine_id": f"golden-{golden_id.lower()}-adapter",
        "version": "1.0.0",
        "title": "Proposed Golden Pack v1 Adapter",
        "label": "TRAINING-ONLY TEST ADAPTER — NOT REAL DOCTRINE",
        "training_only": True,
        "scoring": {
            "max_score": 100,
            "weights": {"detect": 0.35, "classify": 0.30, "assess": 0.0, "respond": 0.35},
            "detection_delay": {
                "excellent_ms": 0,
                "acceptable_ms": 20_000,
                "late_ms": _TIMING_LATE_MS,
            },
        },
        "roe": {"allowed_responses": list(_ALLOWED_RESPONSES), "no_weapon_or_targeting": True},
        "decision_tree": {
            "root_node_id": "detect-node",
            "nodes": [
                {
                    "node_id": "detect-node",
                    "action": "detect",
                    "skill_tags": ["detection"],
                    "expected_values": ["detected"],
                    "branches": {
                        "correct": "classify-node",
                        "incorrect": "classify-node",
                        "timeout": "classify-node",
                    },
                },
                {
                    "node_id": "classify-node",
                    "action": "classify",
                    "skill_tags": ["classification"],
                    "expected_values": [_CLASSIFICATION_MAP[target_class]],
                    "branches": {
                        "correct": "respond-node",
                        "incorrect": "respond-node",
                        "timeout": "respond-node",
                    },
                },
                {
                    "node_id": "respond-node",
                    "action": "respond",
                    "skill_tags": ["response"],
                    "expected_values": best_responses,
                    "branches": {"correct": None, "incorrect": None, "timeout": None},
                },
            ],
        },
    }


def _v1_events(
    *,
    golden_id: str,
    scenario_id: str,
    target_id: str,
    source_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    session_id = str(uuid5(NAMESPACE_URL, f"golden-v1-session:{golden_id}:{target_id}"))
    sequence_by_source_id: dict[str, int] = {}
    converted_by_source_id: dict[str, dict[str, Any]] = {}
    converted: list[dict[str, Any]] = []
    for index, source_event in enumerate(source_events):
        source_id = str(source_event["id"])
        existing = converted_by_source_id.get(source_id)
        if existing is not None:
            converted.append(dict(existing))
            continue
        sequence_by_source_id[source_id] = index
        event_type = {"DETECT": "detect", "CLASSIFY": "classify", "RESPOND": "respond"}[
            source_event["type"]
        ]
        payload: dict[str, Any] = {"target_id": target_id}
        if event_type == "classify":
            payload["classification"] = _map_classification(source_event["value"])
        elif event_type == "respond":
            payload["response"] = _map_response(source_event["value"])
        event = {
            "contract_version": "1.0",
            "event_id": str(
                uuid5(NAMESPACE_URL, f"golden-v1-event:{golden_id}:{target_id}:{source_id}")
            ),
            "session_id": session_id,
            "scenario_id": scenario_id,
            "trainee_id": "golden-trainee",
            "event_type": event_type,
            "t_offset_ms": int(source_event["t_ms"]),
            "sequence": sequence_by_source_id[source_id],
            "payload": payload,
        }
        converted_by_source_id[source_id] = event
        converted.append(dict(event))
    return converted


def _deduplicate_source_events(
    events: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Apply the proposed pack's exact first-event-wins retry semantics."""
    seen: set[str] = set()
    unique_events: list[dict[str, Any]] = []
    duplicates = 0
    for supplied_event in events:
        event = dict(supplied_event)
        _validate_source_event(event)
        source_id = str(event["id"])
        if source_id in seen:
            duplicates += 1
            continue
        seen.add(source_id)
        unique_events.append(event)
    return unique_events, duplicates


def _first_response(events: Iterable[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    responses = [event for event in events if event["type"] == "RESPOND"]
    return min(responses, key=lambda event: int(event["t_ms"])) if responses else None


def _map_classification(value: Any) -> str:
    try:
        return _CLASSIFICATION_MAP[str(value)]
    except KeyError as error:
        raise ProposedGoldenSpecError(f"unsupported golden classification: {value}") from error


def _map_response(value: Any) -> str:
    try:
        return _RESPONSE_MAP[str(value)]
    except KeyError as error:
        raise ProposedGoldenSpecError(f"unsupported golden response: {value}") from error


def _validate_target(target: Mapping[str, Any]) -> None:
    required = {"id", "true_class", "t_visible_ms", "response_zone"}
    if not required.issubset(target):
        raise ProposedGoldenSpecError("golden target is missing required fields")
    if target["response_zone"] not in {"outer", "inner"}:
        raise ProposedGoldenSpecError("golden target response_zone must be 'outer' or 'inner'")
    if int(target["t_visible_ms"]) < 0:
        raise ProposedGoldenSpecError("golden target t_visible_ms must be non-negative")


def _validate_source_event(event: Mapping[str, Any]) -> None:
    required = {"id", "t_ms", "type", "target"}
    if not required.issubset(event):
        raise ProposedGoldenSpecError("golden event is missing required fields")
    if event["type"] not in {"DETECT", "CLASSIFY", "RESPOND"}:
        raise ProposedGoldenSpecError("golden event type is unsupported")
    if int(event["t_ms"]) < 0:
        raise ProposedGoldenSpecError("golden event t_ms must be non-negative")
    if event["type"] in {"CLASSIFY", "RESPOND"} and "value" not in event:
        raise ProposedGoldenSpecError("golden classify/respond event requires value")


def _stable_seed(golden_id: str, target_id: str) -> int:
    """Return a deterministic non-negative integer valid under the v1 schema."""
    return uuid5(NAMESPACE_URL, f"golden-v1-seed:{golden_id}:{target_id}").int % (2**53)
