#!/usr/bin/env python3
"""Automate the API-backed portions of the documented five-minute demo flow.

This intentionally uses the disposable demo seeder and FastAPI's in-process
client. It exercises local login, doctrine listing, ready-session playback
state, durable event ingestion, completion, scoring, replay, and unit views.
It does not execute or claim native Godot interaction/rendering/FPS.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from core.api.app import create_app  # noqa: E402
from core.api.runtime import create_local_services  # noqa: E402

INSTRUCTOR_HEADERS = {"X-Actor-Id": "demo-instructor", "X-Pin": "262471"}
TRAINEE_HEADERS = {"X-Actor-Id": "demo-trainee", "X-Pin": "262472"}


def _require(response: object, label: str) -> dict[str, object] | list[object]:
    status_code = getattr(response, "status_code")
    if status_code != 200:
        raise SystemExit(f"DEMO_SMOKE_FAIL: {label} returned HTTP {status_code}: {response.text}")
    return response.json()


def _seed(database: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "seed_demo.py"),
            "--database",
            str(database),
            "--json",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _record_and_score(
    client: TestClient,
    *,
    session_id: str,
    doctrine_id: str,
    doctrine_version: str,
) -> dict[str, object]:
    snapshot = _require(
        client.get(f"/api/sessions/{session_id}", headers=TRAINEE_HEADERS),
        f"load session {session_id}",
    )
    scenario = snapshot["scenario"]
    target = next(
        target for target in scenario["targets"] if target["affiliation"] == "simulated_threat"
    )
    target_id = target["target_id"]
    start = int(target["t_visible_ms"])
    actions = (
        ("detect", {"target_id": target_id}),
        ("classify", {"target_id": target_id, "classification": "simulated_threat"}),
        ("assess", {"target_id": target_id, "assessment": "high"}),
        ("respond", {"target_id": target_id, "response": "report"}),
    )
    for sequence, (event_type, payload) in enumerate(actions):
        event = {
            "contract_version": scenario["contract_version"],
            "event_id": str(uuid5(NAMESPACE_URL, f"demo-smoke:{session_id}:{event_type}")),
            "session_id": session_id,
            "scenario_id": scenario["scenario_id"],
            "trainee_id": "demo-trainee",
            "event_type": event_type,
            "t_offset_ms": start + 100 * (sequence + 1),
            "sequence": sequence,
            "payload": payload,
        }
        _require(
            client.post("/api/events", headers=TRAINEE_HEADERS, json={"event": event}), event_type
        )

    _require(
        client.post(f"/api/sessions/{session_id}/complete", headers=TRAINEE_HEADERS, json={}),
        f"complete session {session_id}",
    )
    scored = _require(
        client.post(
            f"/api/sessions/{session_id}/score",
            headers=INSTRUCTOR_HEADERS,
            json={"doctrine_id": doctrine_id, "version": doctrine_version},
        ),
        f"score session {session_id}",
    )
    return scored["report"]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sih26247-demo-smoke-") as temporary_directory:
        seeded = _seed(Path(temporary_directory) / "demo.sqlite3")
        services = create_local_services(Path(str(seeded["database"])))
        client = TestClient(create_app(services))

        health = _require(client.get("/api/health"), "health")
        instructor = _require(
            client.post(
                "/api/auth/login",
                json={"user_id": "demo-instructor", "pin": "262471"},
            ),
            "instructor login",
        )
        trainee = _require(
            client.post(
                "/api/auth/login",
                json={"user_id": "demo-trainee", "pin": "262472"},
            ),
            "trainee login",
        )
        doctrines = _require(
            client.get("/api/doctrines", headers=INSTRUCTOR_HEADERS), "doctrine list"
        )
        doctrine = doctrines[0]
        sessions = seeded["sessions"]
        first_session = sessions["01-scripted-clear-single.json"]
        third_session = sessions["03-night-degraded-urban.json"]

        first_report = _record_and_score(
            client,
            session_id=first_session,
            doctrine_id=doctrine["doctrine_id"],
            doctrine_version=doctrine["version"],
        )
        replay = _require(
            client.get(f"/api/sessions/{first_session}/replay/4000", headers=INSTRUCTOR_HEADERS),
            "replay frame",
        )
        second_report = _record_and_score(
            client,
            session_id=third_session,
            doctrine_id=doctrine["doctrine_id"],
            doctrine_version=doctrine["version"],
        )
        trends = _require(client.get("/api/trends", headers=INSTRUCTOR_HEADERS), "unit trends")
        unit = _require(
            client.get("/api/units/demo-unit/summary", headers=INSTRUCTOR_HEADERS),
            "unit summary",
        )

    print("DEMO_SMOKE_OK: seeded three disposable ready sessions")
    print(
        "DEMO_SMOKE_OK: "
        f"health={health['status']} instructor={instructor['role']} trainee={trainee['role']}"
    )
    print(f"DEMO_SMOKE_OK: generic doctrine={doctrine['doctrine_id']}@{doctrine['version']}")
    print(
        "DEMO_SMOKE_OK: scripted score="
        f"{first_report['total_score']} replay_targets={len(replay['targets'])}"
    )
    print(f"DEMO_SMOKE_OK: night-rain score={second_report['total_score']}")
    print(
        "DEMO_SMOKE_OK: unit_completed_sessions="
        f"{unit['trainees'][0]['completed_sessions']} trend_points={len(trends)}"
    )
    print("DEMO_SMOKE_BOUNDARY: native Godot interaction, rendering, and FPS were not run")


if __name__ == "__main__":
    main()
