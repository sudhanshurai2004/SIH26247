#!/usr/bin/env python3
"""Explicit local v1-to-v2 migration for contract payload files.

This utility has no network behavior. It preserves v1 source files and writes
new JSON/YAML output only at paths selected by the local operator.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        payload = yaml.safe_load(source) if path.suffix in {".yaml", ".yml"} else json.load(source)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object payload")
    return payload


def _write(path: Path, payload: MappingLike) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix in {".yaml", ".yml"}:
        path.write_text(yaml.safe_dump(dict(payload), sort_keys=False), encoding="utf-8")
    else:
        path.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
        )


MappingLike = dict[str, Any]


def main() -> None:
    sys.path.insert(0, str(REPOSITORY_ROOT))
    from core.migrations import (  # noqa: PLC0415
        migrate_doctrine_v1_to_v2,
        migrate_event_v1_to_v2,
        migrate_scenario_v1_to_v2,
    )

    parser = argparse.ArgumentParser(
        description="Migrate frozen SIH 26247 contract v1 payloads to v2"
    )
    parser.add_argument("--scenario-input", type=Path)
    parser.add_argument("--scenario-output", type=Path)
    parser.add_argument("--event-input", action="append", type=Path, default=[])
    parser.add_argument("--event-output-dir", type=Path)
    parser.add_argument("--doctrine-input", type=Path)
    parser.add_argument("--doctrine-output", type=Path)
    args = parser.parse_args()

    if bool(args.scenario_input) != bool(args.scenario_output):
        parser.error("--scenario-input and --scenario-output must be supplied together")
    if bool(args.doctrine_input) != bool(args.doctrine_output):
        parser.error("--doctrine-input and --doctrine-output must be supplied together")
    if args.event_input and args.event_output_dir is None:
        parser.error("--event-output-dir is required when --event-input is used")
    if not any((args.scenario_input, args.event_input, args.doctrine_input)):
        parser.error("select at least one scenario, event, or doctrine migration")

    outputs: list[str] = []
    if args.scenario_input:
        assert args.scenario_output
        _write(args.scenario_output, migrate_scenario_v1_to_v2(_load(args.scenario_input)))
        outputs.append(str(args.scenario_output))
    if args.doctrine_input:
        assert args.doctrine_output
        _write(args.doctrine_output, migrate_doctrine_v1_to_v2(_load(args.doctrine_input)))
        outputs.append(str(args.doctrine_output))
    if args.event_input:
        assert args.event_output_dir
        for input_path in args.event_input:
            output_path = args.event_output_dir / input_path.name
            _write(output_path, migrate_event_v1_to_v2(_load(input_path)))
            outputs.append(str(output_path))
    print(json.dumps({"status": "ok", "outputs": outputs}, sort_keys=True))


if __name__ == "__main__":
    main()
