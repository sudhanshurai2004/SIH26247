"""Pure, deterministic scoring of trainee events against an abstract doctrine."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

from core.contracts import ContractValidationError, validate_payload, validate_versioned_payload
from core.scoring.doctrine import DoctrineValidationError, validate_doctrine
from core.serialization import canonical_json


class ScoringError(ValueError):
    """Raised when score inputs cannot be safely evaluated."""


@dataclass(frozen=True)
class NodeResult:
    """Auditable result for one doctrine decision-tree node."""

    node_id: str
    action: str
    skill_tags: tuple[str, ...]
    outcome: str
    event_id: str | None
    target_id: str | None
    detection_delay_ms: int | None
    timing_band: str | None
    max_points: float
    points: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TargetScoreResult:
    """Native v2 per-target result before session aggregation and penalties."""

    target_id: str
    score_fraction: float
    critical_errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScoreReport:
    """Serializable result of a complete decision-tree traversal."""

    scenario_id: str
    doctrine_id: str
    doctrine_version: str
    max_score: int
    total_score: float
    interrupted: bool
    rating_eligible: bool
    node_results: tuple[NodeResult, ...]
    target_results: tuple[TargetScoreResult, ...] = ()
    critical_errors: tuple[str, ...] = ()
    ignored_duplicate_events: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "doctrine_id": self.doctrine_id,
            "doctrine_version": self.doctrine_version,
            "max_score": self.max_score,
            "total_score": self.total_score,
            "interrupted": self.interrupted,
            "rating_eligible": self.rating_eligible,
            "node_results": [result.as_dict() for result in self.node_results],
            "target_results": [result.as_dict() for result in self.target_results],
            "critical_errors": list(self.critical_errors),
            "ignored_duplicate_events": self.ignored_duplicate_events,
        }


def score_scenario(
    scenario: Mapping[str, Any],
    events: Iterable[Mapping[str, Any]],
    doctrine: Mapping[str, Any],
    *,
    interrupted: bool = False,
) -> ScoreReport:
    """Score events with no wall-clock input and no hidden scoring weights.

    Every action contribution is ``doctrine.max_score * doctrine.weight``.
    Detection credit is computed only from doctrine timing thresholds and the
    target's precomputed ``t_visible_ms`` marker, never scenario start time.
    """
    event_list = [dict(event) for event in events]
    contract_version = scenario.get("contract_version")
    if contract_version == "2.0":
        return _score_scenario_v2(scenario, event_list, doctrine, interrupted=interrupted)
    if contract_version != "1.0":
        raise ScoringError(f"unsupported scenario contract_version {contract_version!r}")
    _validate_inputs(scenario, event_list, doctrine)
    event_list = _deduplicate_events(event_list)
    sorted_events = sorted(
        event_list,
        key=lambda event: (event["sequence"], event["t_offset_ms"], event["event_id"]),
    )
    interruption_sequences = [
        event["sequence"] for event in sorted_events if event["event_type"] == "session_interrupted"
    ]
    is_interrupted = interrupted or bool(interruption_sequences)
    if interruption_sequences:
        first_interruption = min(interruption_sequences)
        sorted_events = [event for event in sorted_events if event["sequence"] < first_interruption]

    targets = {target["target_id"]: target for target in scenario["targets"]}
    nodes = {node["node_id"]: node for node in doctrine["decision_tree"]["nodes"]}
    weights = doctrine["scoring"]["weights"]
    max_score = int(doctrine["scoring"]["max_score"])
    allowed_responses = set(doctrine["roe"]["allowed_responses"])

    node_results: list[NodeResult] = []
    current_node_id: str | None = doctrine["decision_tree"]["root_node_id"]
    previous_sequence = -1
    visited: set[str] = set()

    while current_node_id is not None:
        if current_node_id in visited:
            # validate_doctrine rejects cycles. This is a defensive guard for a
            # mutated in-memory mapping supplied by a caller after validation.
            raise ScoringError("doctrine traversal encountered a cycle")
        visited.add(current_node_id)
        node = nodes[current_node_id]
        action = node["action"]
        event = _next_event(sorted_events, action, previous_sequence)
        max_points = round(max_score * float(weights[action]), 6)

        if event is None:
            result = NodeResult(
                node_id=node["node_id"],
                action=action,
                skill_tags=tuple(node["skill_tags"]),
                outcome="timeout",
                event_id=None,
                target_id=None,
                detection_delay_ms=None,
                timing_band=None,
                max_points=max_points,
                points=0.0,
            )
            branch = "timeout"
        else:
            previous_sequence = int(event["sequence"])
            result, branch = _score_event(
                node=node,
                event=event,
                targets=targets,
                doctrine=doctrine,
                allowed_responses=allowed_responses,
                max_points=max_points,
            )

        node_results.append(result)
        current_node_id = node["branches"][branch]

    total_score = round(sum(result.points for result in node_results), 6)
    return ScoreReport(
        scenario_id=str(scenario["scenario_id"]),
        doctrine_id=str(doctrine["doctrine_id"]),
        doctrine_version=str(doctrine["version"]),
        max_score=max_score,
        total_score=total_score,
        interrupted=is_interrupted,
        rating_eligible=not is_interrupted,
        node_results=tuple(node_results),
    )


def _score_scenario_v2(
    scenario: Mapping[str, Any],
    event_list: list[dict[str, Any]],
    doctrine: Mapping[str, Any],
    *,
    interrupted: bool,
) -> ScoreReport:
    """Score native v2 class/zone/critical policy in production, not a sidecar."""
    _validate_v2_inputs(scenario, event_list, doctrine)
    unique_events = _deduplicate_events(event_list)
    ignored_duplicate_events = len(event_list) - len(unique_events)
    sorted_events = sorted(
        unique_events,
        key=lambda event: (event["sequence"], event["t_offset_ms"], event["event_id"]),
    )
    interruption_sequences = [
        event["sequence"] for event in sorted_events if event["event_type"] == "session_interrupted"
    ]
    is_interrupted = interrupted or bool(interruption_sequences)
    if interruption_sequences:
        first_interruption = min(interruption_sequences)
        sorted_events = [event for event in sorted_events if event["sequence"] < first_interruption]

    targets = {str(target["target_id"]): target for target in scenario["targets"]}
    for event in sorted_events:
        if (
            event["event_type"] != "session_interrupted"
            and event["payload"]["target_id"] not in targets
        ):
            raise ScoringError("event target_id does not exist in the scored v2 scenario")

    nodes_by_action = {node["action"]: node for node in doctrine["decision_tree"]["nodes"]}
    weights = doctrine["scoring"]["weights"]
    max_score = int(doctrine["scoring"]["max_score"])
    target_count = len(targets)
    action_scale = max_score / target_count
    allowed_responses = set(doctrine["roe"]["allowed_responses"])
    engagement_actions = set(doctrine["roe"]["engagement_actions"])
    critical_rules = doctrine["scoring"]["critical_rules"]
    protected_classes = set(critical_rules["engage_nonhostile"]["protected_classes"])
    hostile_classes = set(critical_rules["miss_hostile_at_inner_zone"]["hostile_classes"])
    cap_classes = set(doctrine["scoring"]["friendly_score_cap"]["trigger_classes"])

    node_results: list[NodeResult] = []
    target_results: list[TargetScoreResult] = []
    critical_errors: list[str] = []
    friendly_cap_triggered = False

    for target_id, target in targets.items():
        target_events = [
            event
            for event in sorted_events
            if event["event_type"] != "session_interrupted"
            and event["payload"]["target_id"] == target_id
        ]
        per_target, target_nodes, target_critical, triggers_cap = _score_v2_target(
            target=target,
            events=target_events,
            doctrine=doctrine,
            nodes_by_action=nodes_by_action,
            weights=weights,
            action_scale=action_scale,
            allowed_responses=allowed_responses,
            engagement_actions=engagement_actions,
            protected_classes=protected_classes,
            hostile_classes=hostile_classes,
            interrupted=is_interrupted,
        )
        node_results.extend(target_nodes)
        critical_errors.extend(target_critical)
        friendly_cap_triggered = friendly_cap_triggered or (
            triggers_cap and str(target["training_class"]) in cap_classes
        )
        target_results.append(
            TargetScoreResult(
                target_id=target_id,
                score_fraction=round(per_target, 4),
                critical_errors=tuple(target_critical),
            )
        )

    aggregate = doctrine["scoring"]["session_aggregate"]
    if aggregate["method"] != "mean_per_target":  # defensive; schema fixes the method.
        raise ScoringError("unsupported v2 session aggregate method")
    raw_total = max_score * sum(result.score_fraction for result in target_results) / target_count
    critical_penalty = float(critical_rules["engage_nonhostile"]["penalty_points"]) * sum(
        error.startswith("engage_nonhostile:") for error in critical_errors
    ) + float(critical_rules["miss_hostile_at_inner_zone"]["penalty_points"]) * sum(
        error.startswith("miss_hostile_at_inner_zone:") for error in critical_errors
    )
    total_score = max(float(aggregate["floor_score"]), raw_total - critical_penalty)
    if friendly_cap_triggered:
        total_score = min(
            total_score, float(doctrine["scoring"]["friendly_score_cap"]["cap_score"])
        )

    return ScoreReport(
        scenario_id=str(scenario["scenario_id"]),
        doctrine_id=str(doctrine["doctrine_id"]),
        doctrine_version=str(doctrine["version"]),
        max_score=max_score,
        total_score=round(total_score, 2),
        interrupted=is_interrupted,
        rating_eligible=not is_interrupted,
        node_results=tuple(node_results),
        target_results=tuple(target_results),
        critical_errors=tuple(critical_errors),
        ignored_duplicate_events=ignored_duplicate_events,
    )


def _score_v2_target(
    *,
    target: Mapping[str, Any],
    events: list[dict[str, Any]],
    doctrine: Mapping[str, Any],
    nodes_by_action: Mapping[str, Mapping[str, Any]],
    weights: Mapping[str, Any],
    action_scale: float,
    allowed_responses: set[str],
    engagement_actions: set[str],
    protected_classes: set[str],
    hostile_classes: set[str],
    interrupted: bool,
) -> tuple[float, list[NodeResult], list[str], bool]:
    """Evaluate one v2 target against configured class/zone policy."""
    detect_event = _first_target_event(events, "detect")
    classify_event = _first_target_event(events, "classify", after=detect_event)
    assess_event = _first_target_event(events, "assess", after=detect_event)
    respond_event = _first_target_event(events, "respond")
    target_id = str(target["target_id"])
    detection_delay_ms: int | None = None
    detection_credit = 0.0
    timing_credit = 0.0
    if detect_event is not None:
        detection_credit = 1.0
        detection_delay_ms = max(0, int(detect_event["t_offset_ms"]) - int(target["t_visible_ms"]))
        timing_credit = max(
            0.0,
            1.0 - detection_delay_ms / int(doctrine["scoring"]["detection_delay"]["max_ms"]),
        )

    classification_credit = 0.0
    if classify_event is not None:
        classification = str(classify_event["payload"]["classification"])
        if classification == target["training_class"]:
            classification_credit = 1.0
        elif classification in doctrine.get("partial_credit", {}).get(target["training_class"], []):
            classification_credit = 0.5

    assessment_credit = 0.0
    if (
        assess_event is not None
        and assess_event["payload"]["assessment"] == target["assessment_truth"]
    ):
        assessment_credit = 1.0

    response_credit = 0.0
    response_value: str | None = None
    if respond_event is not None:
        response_value = str(respond_event["payload"]["response"])
        response_rule = doctrine["response_matrix"][target["training_class"]][
            target["response_zone"]
        ]
        if detect_event is not None and response_value in allowed_responses:
            if response_value in response_rule["best"]:
                response_credit = 1.0
            elif response_value in response_rule["acceptable"]:
                response_credit = 0.5

    node_results = [
        _v2_node_result(
            node=nodes_by_action["detect"],
            target_id=target_id,
            event=detect_event,
            outcome_credit=(
                float(weights["detect"]) * detection_credit + float(weights["time"]) * timing_credit
            ),
            max_weight=float(weights["detect"]) + float(weights["time"]),
            action_scale=action_scale,
            detection_delay_ms=detection_delay_ms,
            timing_band=_v2_timing_band(timing_credit, detect_event),
        ),
        _v2_node_result(
            node=nodes_by_action["classify"],
            target_id=target_id,
            event=classify_event,
            outcome_credit=float(weights["classify"]) * classification_credit,
            max_weight=float(weights["classify"]),
            action_scale=action_scale,
        ),
        _v2_node_result(
            node=nodes_by_action["assess"],
            target_id=target_id,
            event=assess_event,
            outcome_credit=float(weights["assess"]) * assessment_credit,
            max_weight=float(weights["assess"]),
            action_scale=action_scale,
        ),
        _v2_node_result(
            node=nodes_by_action["respond"],
            target_id=target_id,
            event=respond_event,
            outcome_credit=float(weights["respond"]) * response_credit,
            max_weight=float(weights["respond"]),
            action_scale=action_scale,
        ),
    ]
    target_score = (
        float(weights["detect"]) * detection_credit
        + float(weights["classify"]) * classification_credit
        + float(weights["assess"]) * assessment_credit
        + float(weights["respond"]) * response_credit
        + float(weights["time"]) * timing_credit
    )
    critical_errors: list[str] = []
    target_class = str(target["training_class"])
    response_is_engagement = response_value is not None and response_value in engagement_actions
    if response_is_engagement and target_class in protected_classes:
        critical_errors.append(f"engage_nonhostile:{target_id}")
    if (
        not interrupted
        and target_class in hostile_classes
        and bool(target["reaches_inner"])
        and target["response_zone"] == "inner"
        and respond_event is None
    ):
        critical_errors.append(f"miss_hostile_at_inner_zone:{target_id}")
    return target_score, node_results, critical_errors, response_is_engagement


def _first_target_event(
    events: Iterable[Mapping[str, Any]],
    action: str,
    *,
    after: Mapping[str, Any] | None = None,
) -> Mapping[str, Any] | None:
    """Return the earliest target action, optionally no earlier than another action."""
    candidates = [event for event in events if event["event_type"] == action]
    if after is not None:
        candidates = [event for event in candidates if event["t_offset_ms"] >= after["t_offset_ms"]]
    if not candidates:
        return None
    return min(
        candidates, key=lambda event: (event["t_offset_ms"], event["sequence"], event["event_id"])
    )


def _v2_node_result(
    *,
    node: Mapping[str, Any],
    target_id: str,
    event: Mapping[str, Any] | None,
    outcome_credit: float,
    max_weight: float,
    action_scale: float,
    detection_delay_ms: int | None = None,
    timing_band: str | None = None,
) -> NodeResult:
    """Create one auditable per-target v2 action result."""
    if event is None:
        outcome = "timeout"
    elif outcome_credit <= 0:
        outcome = "incorrect"
    elif outcome_credit < max_weight:
        outcome = "partial"
    else:
        outcome = "correct"
    return NodeResult(
        node_id=f"{node['node_id']}--{target_id}",
        action=str(node["action"]),
        skill_tags=tuple(node["skill_tags"]),
        outcome=outcome,
        event_id=str(event["event_id"]) if event is not None else None,
        target_id=target_id,
        detection_delay_ms=detection_delay_ms,
        timing_band=timing_band,
        max_points=round(action_scale * max_weight, 6),
        points=round(action_scale * outcome_credit, 6),
    )


def _v2_timing_band(timing_credit: float, detect_event: Mapping[str, Any] | None) -> str | None:
    if detect_event is None:
        return None
    if timing_credit >= 1.0:
        return "excellent"
    if timing_credit > 0:
        return "late"
    return "missed"


def _validate_v2_inputs(
    scenario: Mapping[str, Any],
    events: Iterable[Mapping[str, Any]],
    doctrine: Mapping[str, Any],
) -> None:
    """Validate v2 payload versions before native class/zone scoring."""
    try:
        validate_versioned_payload("scenario", scenario)
        validate_doctrine(doctrine)
        if doctrine.get("contract_version") != "2.0":
            raise ScoringError("scenario and doctrine contract_version must match")
        for event in events:
            validate_versioned_payload("event", event)
            if event.get("contract_version") != "2.0":
                raise ScoringError("scenario and event contract_version must match")
            if event["scenario_id"] != scenario["scenario_id"]:
                raise ScoringError("event scenario_id does not match the scored scenario")
            if event["t_offset_ms"] > scenario["duration_ms"]:
                raise ScoringError("event t_offset_ms exceeds scenario duration")
    except (ContractValidationError, DoctrineValidationError) as error:
        raise ScoringError(str(error)) from error


def _validate_inputs(
    scenario: Mapping[str, Any],
    events: Iterable[Mapping[str, Any]],
    doctrine: Mapping[str, Any],
) -> None:
    """Validate untrusted contract-shaped values before indexing their fields."""
    try:
        validate_payload("scenario", scenario)
        validate_doctrine(doctrine)
        if doctrine.get("contract_version") != "1.0":
            raise ScoringError("scenario and doctrine contract_version must match")
        for event in events:
            validate_payload("event", event)
            if event.get("contract_version") != "1.0":
                raise ScoringError("scenario and event contract_version must match")
            if event["scenario_id"] != scenario["scenario_id"]:
                raise ScoringError("event scenario_id does not match the scored scenario")
            if event["t_offset_ms"] > scenario["duration_ms"]:
                raise ScoringError("event t_offset_ms exceeds scenario duration")
    except (ContractValidationError, DoctrineValidationError) as error:
        raise ScoringError(str(error)) from error


def _deduplicate_events(events: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Apply event-ID idempotency even when scoring is used outside sessions.

    The database service already treats an identical retry as idempotent and
    rejects a reused ID with changed content. Keeping the same rule in this
    pure function makes exported/offline event-log scoring equally safe.
    """
    canonical_by_id: dict[str, str] = {}
    unique_events: list[dict[str, Any]] = []
    for supplied_event in events:
        event = dict(supplied_event)
        event_id = str(event["event_id"])
        encoded = canonical_json(event)
        existing = canonical_by_id.get(event_id)
        if existing is None:
            canonical_by_id[event_id] = encoded
            unique_events.append(event)
        elif existing != encoded:
            raise ScoringError("event_id is already bound to a different payload")
    return unique_events


def _next_event(
    events: list[dict[str, Any]], action: str, previous_sequence: int
) -> dict[str, Any] | None:
    """Use the first matching trainee action after the preceding tree action."""
    for event in events:
        if event["event_type"] == action and event["sequence"] > previous_sequence:
            return event
    return None


def _score_event(
    *,
    node: Mapping[str, Any],
    event: Mapping[str, Any],
    targets: Mapping[str, Mapping[str, Any]],
    doctrine: Mapping[str, Any],
    allowed_responses: set[str],
    max_points: float,
) -> tuple[NodeResult, str]:
    """Score one event and return the result plus its decision-tree branch."""
    action = str(node["action"])
    payload = event["payload"]
    target_id = str(payload.get("target_id")) if "target_id" in payload else None
    event_value = _event_value(action, payload)
    correct = event_value in node["expected_values"]
    detection_delay_ms: int | None = None
    timing_band: str | None = None
    credit = 1.0

    if action == "detect":
        target = targets.get(target_id or "")
        if target is None:
            correct = False
            timing_band = "unknown_target"
            credit = 0.0
        else:
            detection_delay_ms = int(event["t_offset_ms"]) - int(target["t_visible_ms"])
            timing_band, credit = _detection_credit(
                detection_delay_ms,
                doctrine["scoring"]["detection_delay"],
            )
            if detection_delay_ms < 0:
                correct = False

    if action == "respond" and event_value not in allowed_responses:
        correct = False

    points = round(max_points * credit, 6) if correct else 0.0
    outcome = "correct" if correct else "incorrect"
    return (
        NodeResult(
            node_id=str(node["node_id"]),
            action=action,
            skill_tags=tuple(node["skill_tags"]),
            outcome=outcome,
            event_id=str(event["event_id"]),
            target_id=target_id,
            detection_delay_ms=detection_delay_ms,
            timing_band=timing_band,
            max_points=max_points,
            points=points,
        ),
        outcome,
    )


def _event_value(action: str, payload: Mapping[str, Any]) -> str:
    """Extract the abstract value compared with the doctrine's expected values."""
    if action == "detect":
        return "detected"
    value_key = {
        "classify": "classification",
        "assess": "assessment",
        "respond": "response",
    }[action]
    return str(payload[value_key])


def _detection_credit(delay_ms: int, thresholds: Mapping[str, Any]) -> tuple[str, float]:
    """Return a threshold-only timing band and continuous credit.

    The frozen v1 doctrine exposes timing thresholds but no additional scoring
    coefficients. To avoid inventing another weight, credit falls linearly from
    1.0 at ``excellent_ms`` to 0.0 at ``late_ms``. ``acceptable_ms`` remains an
    auditable band boundary in the AAR result.
    """
    excellent_ms = int(thresholds["excellent_ms"])
    acceptable_ms = int(thresholds["acceptable_ms"])
    late_ms = int(thresholds["late_ms"])
    if delay_ms < 0:
        return "before_visible", 0.0
    if delay_ms <= excellent_ms:
        return "excellent", 1.0
    if delay_ms <= acceptable_ms:
        band = "acceptable"
    elif delay_ms <= late_ms:
        band = "late"
    else:
        return "missed", 0.0

    # Doctrine validation ensures late_ms > excellent_ms.
    credit = (late_ms - delay_ms) / (late_ms - excellent_ms)
    return band, round(max(0.0, min(1.0, credit)), 6)
