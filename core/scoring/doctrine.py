"""Validated loading and semantic checks for abstract training doctrine."""

from __future__ import annotations

from collections.abc import Mapping
from math import isclose
from pathlib import Path
from typing import Any

import yaml

from core.contracts import (
    ContractValidationError,
    load_and_validate_versioned,
    validate_versioned_payload,
)


class DoctrineValidationError(ValueError):
    """Raised when a doctrine is structurally valid but not executable."""


def load_doctrine(path: Path) -> dict[str, Any]:
    """Safely load a local YAML doctrine and check its executable semantics."""
    try:
        doctrine = load_and_validate_versioned("doctrine", path)
    except ContractValidationError as error:
        raise DoctrineValidationError(str(error)) from error
    if not isinstance(doctrine, dict):
        raise DoctrineValidationError("doctrine root must be an object")
    validate_doctrine(doctrine)
    return doctrine


def parse_doctrine_text(yaml_text: str) -> dict[str, Any]:
    """Safely parse and validate uploaded doctrine text without executing YAML tags."""
    try:
        doctrine = yaml.safe_load(yaml_text)
    except yaml.YAMLError as error:
        raise DoctrineValidationError("doctrine YAML could not be parsed safely") from error
    if not isinstance(doctrine, dict):
        raise DoctrineValidationError("doctrine root must be an object")
    validate_doctrine(doctrine)
    return doctrine


def validate_doctrine(doctrine: Mapping[str, Any]) -> None:
    """Validate a versioned doctrine plus executable scoring invariants."""
    try:
        validate_versioned_payload("doctrine", doctrine)
    except ContractValidationError as error:
        raise DoctrineValidationError(str(error)) from error

    if doctrine["contract_version"] == "2.0":
        _validate_v2_doctrine(doctrine)
        return

    errors: list[str] = []
    weights = doctrine["scoring"]["weights"]
    if not isclose(sum(float(value) for value in weights.values()), 1.0, abs_tol=1e-9):
        errors.append("scoring weights must sum to 1.0")

    delay = doctrine["scoring"]["detection_delay"]
    if not (delay["excellent_ms"] <= delay["acceptable_ms"] <= delay["late_ms"]):
        errors.append("detection-delay thresholds must be ordered excellent <= acceptable <= late")
    if delay["excellent_ms"] == delay["late_ms"]:
        errors.append("excellent_ms and late_ms must not be equal")

    tree = doctrine["decision_tree"]
    nodes = tree["nodes"]
    node_ids = [node["node_id"] for node in nodes]
    known_ids = set(node_ids)
    if len(known_ids) != len(node_ids):
        errors.append("decision-tree node_id values must be unique")
    if tree["root_node_id"] not in known_ids:
        errors.append("decision-tree root_node_id must refer to a node")

    allowed_responses = set(doctrine["roe"]["allowed_responses"])
    for node in nodes:
        for branch_id in node["branches"].values():
            if branch_id is not None and branch_id not in known_ids:
                errors.append(
                    f"node '{node['node_id']}' has an unknown branch target '{branch_id}'"
                )
        if node["action"] == "respond" and not set(node["expected_values"]).issubset(
            allowed_responses
        ):
            errors.append(
                f"respond node '{node['node_id']}' expects a response outside the doctrine ROE"
            )

    if not errors:
        _assert_acyclic_tree(tree["root_node_id"], nodes)
    if errors:
        raise DoctrineValidationError("; ".join(errors))


def _validate_v2_doctrine(doctrine: Mapping[str, Any]) -> None:
    """Validate native v2 class/zone/penalty policy without operational content."""
    errors: list[str] = []
    scoring = doctrine["scoring"]
    weights = scoring["weights"]
    if not isclose(sum(float(value) for value in weights.values()), 1.0, abs_tol=1e-9):
        errors.append("scoring weights must sum to 1.0")
    if float(scoring["session_aggregate"]["floor_score"]) > float(scoring["max_score"]):
        errors.append("session aggregate floor_score must not exceed max_score")
    if float(scoring["friendly_score_cap"]["cap_score"]) > float(scoring["max_score"]):
        errors.append("friendly_score_cap cap_score must not exceed max_score")

    classes = set(doctrine["classes"])
    response_matrix = doctrine["response_matrix"]
    if set(response_matrix) != classes:
        errors.append("response_matrix must define exactly the declared classes")
    partial_credit = doctrine.get("partial_credit", {})
    for target_class, accepted_classes in partial_credit.items():
        if target_class not in classes or not set(accepted_classes).issubset(classes):
            errors.append("partial_credit must only reference declared classes")

    allowed_responses = set(doctrine["roe"]["allowed_responses"])
    engagement_actions = set(doctrine["roe"]["engagement_actions"])
    if not engagement_actions.issubset(allowed_responses):
        errors.append("engagement_actions must be included in allowed_responses")
    for class_rule in response_matrix.values():
        for zone_rule in class_rule.values():
            responses = set(zone_rule["best"]) | set(zone_rule["acceptable"])
            if not responses.issubset(allowed_responses):
                errors.append("response_matrix responses must be included in allowed_responses")
            if set(zone_rule["best"]) & set(zone_rule["acceptable"]):
                errors.append("response_matrix best and acceptable responses must not overlap")

    critical_rules = scoring["critical_rules"]
    protected_classes = set(critical_rules["engage_nonhostile"]["protected_classes"])
    hostile_classes = set(critical_rules["miss_hostile_at_inner_zone"]["hostile_classes"])
    cap_classes = set(scoring["friendly_score_cap"]["trigger_classes"])
    if not (protected_classes | hostile_classes | cap_classes).issubset(classes):
        errors.append("critical rules and friendly cap must only reference declared classes")

    tree = doctrine["decision_tree"]
    _validate_tree(tree, allowed_responses, errors)
    required_actions = {"detect", "classify", "assess", "respond"}
    if {node["action"] for node in tree["nodes"]} != required_actions:
        errors.append("v2 decision_tree must define exactly detect/classify/assess/respond actions")
    if errors:
        raise DoctrineValidationError("; ".join(errors))


def _validate_tree(tree: Mapping[str, Any], allowed_responses: set[str], errors: list[str]) -> None:
    """Apply shared action-tree integrity checks used by both contract versions."""
    nodes = tree["nodes"]
    node_ids = [node["node_id"] for node in nodes]
    known_ids = set(node_ids)
    if len(known_ids) != len(node_ids):
        errors.append("decision-tree node_id values must be unique")
    if tree["root_node_id"] not in known_ids:
        errors.append("decision-tree root_node_id must refer to a node")

    for node in nodes:
        for branch_id in node["branches"].values():
            if branch_id is not None and branch_id not in known_ids:
                errors.append(
                    f"node '{node['node_id']}' has an unknown branch target '{branch_id}'"
                )
        if node["action"] == "respond" and not set(node["expected_values"]).issubset(
            allowed_responses
        ):
            errors.append(
                f"respond node '{node['node_id']}' expects a response outside the doctrine ROE"
            )

    if not errors:
        _assert_acyclic_tree(tree["root_node_id"], nodes)


def _assert_acyclic_tree(root_node_id: str, nodes: list[Mapping[str, Any]]) -> None:
    """Reject loops so a malformed editable doctrine cannot score indefinitely."""
    by_id = {node["node_id"]: node for node in nodes}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise DoctrineValidationError("decision tree must not contain a cycle")
        if node_id in visited:
            return
        visiting.add(node_id)
        for child_id in by_id[node_id]["branches"].values():
            if child_id is not None:
                visit(child_id)
        visiting.remove(node_id)
        visited.add(node_id)

    visit(root_node_id)
