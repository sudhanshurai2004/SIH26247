"""Bundled offline Godot scenario-pack smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

from core.generator import validate_scenario

ROOT = Path(__file__).resolve().parents[1]


def test_godot_project_has_2d_entrypoint_and_optional_3d_scene() -> None:
    project = (ROOT / "client" / "project.godot").read_text(encoding="utf-8")

    assert 'run/main_scene="res://2d/Main2D.tscn"' in project
    scene = (ROOT / "client" / "2d" / "Main2D.tscn").read_text(encoding="utf-8")
    bridge = (ROOT / "client" / "2d" / "local_api_bridge.gd").read_text(encoding="utf-8")
    recorder = (ROOT / "client" / "2d" / "event_recorder.gd").read_text(encoding="utf-8")
    smoke = (ROOT / "client" / "tests" / "headless_smoke.gd").read_text(encoding="utf-8")

    assert (ROOT / "client" / "2d" / "Main2D.tscn").is_file()
    assert (ROOT / "client" / "scenes3d" / "Main3D.tscn").is_file()
    assert 'name="LocalApiBridge"' in scene
    assert "func sync_outbox" in bridge
    assert "func outbox_events" in recorder
    assert "GODOT_SMOKE_OK:" in smoke
    assert "record_detect" in smoke


def test_bundled_v0_pack_contains_valid_playback_scenarios() -> None:
    pack = json.loads((ROOT / "client" / "scenarios" / "pack-v0.json").read_text(encoding="utf-8"))

    assert pack["pack_version"] == "1.0"
    assert pack["scenarios"]
    for scenario in pack["scenarios"]:
        validate_scenario(scenario)
