"""Additive contract-v2 and explicit v1-to-v2 migration regression tests."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from core.contracts import (
    CONTRACTS_DIR,
    ContractValidationError,
    load_json_file,
    load_yaml_file,
    validate_versioned_payload,
    validator_for,
)
from core.migrations.v1_to_v2 import (
    MigrationError,
    migrate_doctrine_v1_to_v2,
    migrate_event_v1_to_v2,
    migrate_scenario_v1_to_v2,
)

SAMPLES_DIR = CONTRACTS_DIR / "samples"
ROOT = CONTRACTS_DIR.parent


@pytest.mark.parametrize("contract", ["scenario_v2", "event_v2", "doctrine_v2"])
def test_v2_schemas_are_independent_valid_draft_2020_12_contracts(contract: str) -> None:
    assert validator_for(contract) is not None


def test_frozen_v1_schema_digests_remain_at_the_additive_v2_boundary() -> None:
    expected = {
        line.split()[1]: line.split()[0]
        for line in (CONTRACTS_DIR / "v1_contracts.sha256").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }
    assert expected
    for relative_path, digest in expected.items():
        payload = (ROOT / relative_path).read_bytes()
        assert sha256(payload).hexdigest() == digest


def test_explicit_v1_to_v2_migration_preserves_source_payloads_and_validates_outputs() -> None:
    scenario = load_json_file(SAMPLES_DIR / "scenario.valid.json")
    event = load_json_file(SAMPLES_DIR / "event.valid.json")
    doctrine = load_yaml_file(ROOT / "doctrine" / "generic_demo.yaml")
    source_snapshot = deepcopy((scenario, event, doctrine))

    migrated_scenario = migrate_scenario_v1_to_v2(scenario)
    migrated_event = migrate_event_v1_to_v2(event)
    migrated_doctrine = migrate_doctrine_v1_to_v2(doctrine)

    assert (scenario, event, doctrine) == source_snapshot
    assert migrated_scenario["contract_version"] == "2.0"
    assert migrated_event["contract_version"] == "2.0"
    assert migrated_doctrine["contract_version"] == "2.0"
    assert migrated_scenario["targets"][0]["response_zone"] == "outer"
    assert migrated_scenario["targets"][0]["reaches_inner"] is False
    assert (
        migrated_doctrine["scoring"]["critical_rules"]["engage_nonhostile"]["penalty_points"] == 0
    )
    assert migrated_doctrine["scoring"]["friendly_score_cap"]["cap_score"] == 100
    validate_versioned_payload("scenario", migrated_scenario)
    validate_versioned_payload("event", migrated_event)
    validate_versioned_payload("doctrine", migrated_doctrine)


def test_migration_refuses_unknown_target_override_and_non_v1_source() -> None:
    scenario = load_json_file(SAMPLES_DIR / "scenario.valid.json")
    with pytest.raises(MigrationError, match="unknown IDs"):
        migrate_scenario_v1_to_v2(scenario, target_overrides={"not-a-target": {}})

    scenario["contract_version"] = "2.0"
    with pytest.raises(MigrationError, match="requires contract_version '1.0'"):
        migrate_scenario_v1_to_v2(scenario)


def test_version_dispatch_rejects_missing_or_unknown_contract_version() -> None:
    with pytest.raises(ContractValidationError, match="unsupported contract_version"):
        validate_versioned_payload("scenario", {"scenario_id": "missing-version"})
