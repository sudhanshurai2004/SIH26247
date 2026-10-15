"""Additive, explicit migration from frozen contract v1 payloads to v2.

V1 intentionally did not represent per-target training class, response zone,
protected-zone outcome, class response matrix, or critical-error policy. The
migration therefore preserves all v1 fields and adds conservative generic
placeholder values; callers can supply per-target overrides when such synthetic
training metadata is known. It never infers or imports real doctrine.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from core.contracts import ContractValidationError, validate_payload, validate_versioned_payload

V2_CONTRACT_VERSION = "2.0"
_GENERIC_CLASSES = (
    "simulated_threat",
    "bird",
    "civil_uas",
    "friendly_aircraft",
    "balloon",
    "other",
)
_ALLOWED_TARGET_OVERRIDE_KEYS = {
    "training_class",
    "assessment_truth",
    "response_zone",
    "reaches_inner",
}


class MigrationError(ValueError):
    """Raised when a v1 payload cannot be migrated safely and explicitly."""


def migrate_scenario_v1_to_v2(
    scenario: Mapping[str, Any],
    *,
    target_overrides: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a v2 scenario while retaining every v1 trajectory/timing field.

    ``target_overrides`` may set only the v2 additions for a target. Without an
    override, migration uses generic synthetic defaults: an outer zone and no
    inner-zone reach, because v1 never encoded zone progression.
    """
    _validate_v1("scenario", scenario)
    overrides = target_overrides or {}
    migrated = deepcopy(dict(scenario))
    migrated["contract_version"] = V2_CONTRACT_VERSION
    migrated_targets: list[dict[str, Any]] = []
    seen_override_ids: set[str] = set()
    for source_target in scenario["targets"]:
        target = deepcopy(dict(source_target))
        target_id = str(target["target_id"])
        override = dict(overrides.get(target_id, {}))
        unknown_keys = set(override) - _ALLOWED_TARGET_OVERRIDE_KEYS
        if unknown_keys:
            raise MigrationError(f"unsupported v2 target override fields: {sorted(unknown_keys)}")
        seen_override_ids.add(target_id)
        target.update(
            {
                "training_class": _default_training_class(target),
                "assessment_truth": "high",
                "response_zone": "outer",
                "reaches_inner": False,
            }
        )
        target.update(override)
        migrated_targets.append(target)
    unknown_target_ids = set(overrides) - seen_override_ids
    if unknown_target_ids:
        raise MigrationError(
            f"target overrides reference unknown IDs: {sorted(unknown_target_ids)}"
        )
    migrated["targets"] = migrated_targets
    _validate_v2("scenario", migrated)
    return migrated


def migrate_event_v1_to_v2(event: Mapping[str, Any]) -> dict[str, Any]:
    """Promote a contract-valid abstract v1 trainee event to v2 unchanged otherwise."""
    _validate_v1("event", event)
    migrated = deepcopy(dict(event))
    migrated["contract_version"] = V2_CONTRACT_VERSION
    _validate_v2("event", migrated)
    return migrated


def migrate_doctrine_v1_to_v2(
    doctrine: Mapping[str, Any],
    *,
    version: str = "2.0.0",
) -> dict[str, Any]:
    """Convert a v1 generic placeholder into an executable generic v2 placeholder.

    New v2 penalties are zero and the cap equals ``max_score`` so this migration
    does not invent punitive policy absent from v1. The generic matrix merely
    supplies safe abstract UI/scoring defaults; it is not real doctrine.
    """
    _validate_v1("doctrine", doctrine)
    scoring = doctrine["scoring"]
    weights = scoring["weights"]
    allowed_responses = list(doctrine["roe"]["allowed_responses"])
    response_matrix = _generic_response_matrix(allowed_responses)
    max_score = int(scoring["max_score"])
    migrated: dict[str, Any] = {
        "contract_version": V2_CONTRACT_VERSION,
        "doctrine_id": str(doctrine["doctrine_id"]),
        "version": version,
        "title": f"{doctrine['title']} (v2 generic migration)",
        "label": "GENERIC V2 MIGRATION PLACEHOLDER — TRAINING ONLY; NOT REAL DOCTRINE",
        "training_only": True,
        "classes": list(_GENERIC_CLASSES),
        "partial_credit": {},
        "scoring": {
            "max_score": max_score,
            "weights": {
                "detect": float(weights["detect"]),
                "classify": float(weights["classify"]),
                "assess": float(weights["assess"]),
                "respond": float(weights["respond"]),
                "time": 0.0,
            },
            "detection_delay": {"max_ms": int(scoring["detection_delay"]["late_ms"])},
            "session_aggregate": {"method": "mean_per_target", "floor_score": 0},
            "critical_rules": {
                "engage_nonhostile": {
                    "penalty_points": 0,
                    "protected_classes": [
                        "bird",
                        "civil_uas",
                        "friendly_aircraft",
                        "balloon",
                        "other",
                    ],
                },
                "miss_hostile_at_inner_zone": {
                    "penalty_points": 0,
                    "hostile_classes": ["simulated_threat"],
                },
            },
            "friendly_score_cap": {
                "cap_score": max_score,
                "trigger_classes": ["friendly_aircraft"],
            },
        },
        "roe": {
            "allowed_responses": allowed_responses,
            "engagement_actions": [],
            "no_weapon_or_targeting": True,
        },
        "response_matrix": response_matrix,
        "decision_tree": deepcopy(doctrine["decision_tree"]),
    }
    _validate_v2("doctrine", migrated)
    return migrated


def _default_training_class(target: Mapping[str, Any]) -> str:
    if target["affiliation"] == "simulated_threat":
        return "simulated_threat"
    entity_class = str(target["entity_class"])
    if entity_class in _GENERIC_CLASSES:
        return entity_class
    return "other"


def _generic_response_matrix(allowed_responses: list[str]) -> dict[str, Any]:
    if not allowed_responses:
        raise MigrationError("v1 doctrine must have at least one allowed response")
    monitor = "monitor" if "monitor" in allowed_responses else allowed_responses[0]
    report = "report" if "report" in allowed_responses else monitor
    escalate = "escalate" if "escalate" in allowed_responses else report
    return {
        "simulated_threat": {
            "outer": {"best": [report], "acceptable": [monitor] if monitor != report else []},
            "inner": {"best": [escalate], "acceptable": [report] if report != escalate else []},
        },
        "bird": {
            "outer": {"best": [monitor], "acceptable": []},
            "inner": {"best": [monitor], "acceptable": []},
        },
        "civil_uas": {
            "outer": {"best": [report], "acceptable": [monitor] if monitor != report else []},
            "inner": {"best": [report], "acceptable": [monitor] if monitor != report else []},
        },
        "friendly_aircraft": {
            "outer": {"best": [monitor], "acceptable": []},
            "inner": {"best": [monitor], "acceptable": []},
        },
        "balloon": {
            "outer": {"best": [monitor], "acceptable": []},
            "inner": {"best": [monitor], "acceptable": []},
        },
        "other": {
            "outer": {"best": [monitor], "acceptable": []},
            "inner": {"best": [monitor], "acceptable": []},
        },
    }


def _validate_v1(kind: str, payload: Mapping[str, Any]) -> None:
    if payload.get("contract_version") != "1.0":
        raise MigrationError(f"{kind} migration requires contract_version '1.0'")
    try:
        validate_payload(kind, payload)  # type: ignore[arg-type]
    except ContractValidationError as error:
        raise MigrationError(str(error)) from error


def _validate_v2(kind: str, payload: Mapping[str, Any]) -> None:
    try:
        validate_versioned_payload(kind, payload)  # type: ignore[arg-type]
    except ContractValidationError as error:
        raise MigrationError(str(error)) from error
