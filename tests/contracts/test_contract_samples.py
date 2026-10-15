"""Contract fixtures are executable examples of the frozen Stage 1 interface."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from core.contracts import (
    CONTRACTS_DIR,
    SCHEMA_PATHS,
    ContractValidationError,
    load_and_validate,
    load_json_file,
    load_yaml_file,
    validate_payload,
    validator_for,
)

SAMPLES_DIR = CONTRACTS_DIR / "samples"


@pytest.mark.parametrize("contract", ["scenario", "event", "doctrine"])
def test_schema_is_valid_draft_2020_12(contract: str) -> None:
    """Each checked validator proves the local schema passes its meta-schema."""
    assert validator_for(contract) is not None


@pytest.mark.parametrize(
    ("contract", "filename"),
    [
        ("scenario", "scenario.valid.json"),
        ("event", "event.valid.json"),
        ("doctrine", "doctrine.valid.yaml"),
    ],
)
def test_valid_sample_satisfies_its_contract(contract: str, filename: str) -> None:
    load_and_validate(contract, SAMPLES_DIR / filename)


@pytest.mark.parametrize(
    ("contract", "filename"),
    [
        ("scenario", "scenario.invalid.json"),
        ("event", "event.invalid.json"),
        ("doctrine", "doctrine.invalid.yaml"),
    ],
)
def test_invalid_sample_is_rejected(contract: str, filename: str) -> None:
    with pytest.raises(ContractValidationError):
        load_and_validate(contract, SAMPLES_DIR / filename)


def test_generic_demo_doctrine_is_a_valid_contract_payload() -> None:
    doctrine_path = CONTRACTS_DIR.parents[0] / "doctrine" / "generic_demo.yaml"
    load_and_validate("doctrine", doctrine_path)


def test_uuid_format_is_enforced_for_event_ids() -> None:
    event = load_json_file(SAMPLES_DIR / "event.valid.json")
    event["event_id"] = "not-a-uuid"

    with pytest.raises(ContractValidationError, match="event_id"):
        validate_payload("event", event)


def test_yaml_loader_rejects_python_object_tags(tmp_path: Path) -> None:
    unsafe_yaml = tmp_path / "unsafe.yaml"
    unsafe_yaml.write_text("!!python/object/apply:os.system ['echo unsafe']", encoding="utf-8")

    with pytest.raises(yaml.YAMLError):
        load_yaml_file(unsafe_yaml)


def test_schema_paths_are_confined_to_contracts_directory() -> None:
    assert all(path.parent == CONTRACTS_DIR for path in SCHEMA_PATHS.values())
