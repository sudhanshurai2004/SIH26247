"""Local contract loading and validation helpers.

The helpers deliberately use only repository files and ``yaml.safe_load``.
They are the single validation path that later upload endpoints will use.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any, Literal

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ContractName = Literal[
    "scenario",
    "event",
    "doctrine",
    "scenario_v2",
    "event_v2",
    "doctrine_v2",
]

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = REPOSITORY_ROOT / "contracts"
SCHEMA_PATHS: dict[ContractName, Path] = {
    "scenario": CONTRACTS_DIR / "scenario.schema.json",
    "event": CONTRACTS_DIR / "event.schema.json",
    "doctrine": CONTRACTS_DIR / "doctrine.schema.json",
    "scenario_v2": CONTRACTS_DIR / "scenario_v2.schema.json",
    "event_v2": CONTRACTS_DIR / "event_v2.schema.json",
    "doctrine_v2": CONTRACTS_DIR / "doctrine_v2.schema.json",
}


class ContractValidationError(ValueError):
    """Raised when a payload does not satisfy a frozen contract."""


def load_json_file(path: Path) -> Any:
    """Load a UTF-8 JSON fixture without performing validation."""
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def load_yaml_file(path: Path) -> Any:
    """Load YAML safely; object construction tags are never executed."""
    with path.open(encoding="utf-8") as source:
        return yaml.safe_load(source)


@cache
def validator_for(contract: ContractName) -> Draft202012Validator:
    """Return a checked Draft 2020-12 validator for one local contract."""
    schema = load_json_file(SCHEMA_PATHS[contract])
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_payload(contract: ContractName, payload: Any) -> None:
    """Validate *payload* or raise one deterministic, readable error."""
    errors = sorted(
        validator_for(contract).iter_errors(payload),
        key=lambda error: (tuple(str(part) for part in error.absolute_path), error.message),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ContractValidationError(f"{contract} contract invalid at {location}: {error.message}")


def versioned_contract_name(
    base_contract: Literal["scenario", "event", "doctrine"], payload: Any
) -> ContractName:
    """Select a frozen schema from an explicit payload version without guessing.

    V1 names remain the default schema names for compatibility. V2 is a new,
    additive family; callers must pass a concrete ``contract_version`` field.
    """
    if not isinstance(payload, dict):
        raise ContractValidationError(f"{base_contract} contract payload must be an object")
    version = payload.get("contract_version")
    if version == "1.0":
        return base_contract
    if version == "2.0":
        return f"{base_contract}_v2"  # type: ignore[return-value]
    raise ContractValidationError(
        f"{base_contract} contract has unsupported contract_version {version!r}"
    )


def validate_versioned_payload(
    base_contract: Literal["scenario", "event", "doctrine"], payload: Any
) -> None:
    """Validate a v1 or v2 payload selected solely by ``contract_version``."""
    validate_payload(versioned_contract_name(base_contract, payload), payload)


def load_and_validate(contract: ContractName, path: Path) -> Any:
    """Load a local JSON/YAML payload and validate it against its contract."""
    payload = load_yaml_file(path) if path.suffix in {".yaml", ".yml"} else load_json_file(path)
    validate_payload(contract, payload)
    return payload


def load_and_validate_versioned(
    base_contract: Literal["scenario", "event", "doctrine"], path: Path
) -> Any:
    """Load a v1/v2 JSON or YAML payload and validate its declared version."""
    payload = load_yaml_file(path) if path.suffix in {".yaml", ".yml"} else load_json_file(path)
    validate_versioned_payload(base_contract, payload)
    return payload
