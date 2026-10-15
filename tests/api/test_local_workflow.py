"""Local API workflow: bootstrap, seed, session, events, score, AAR, replay."""

from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from fastapi.testclient import TestClient

from core.api.app import create_app
from core.api.runtime import create_local_services


def _headers(user_id: str, pin: str) -> dict[str, str]:
    return {"X-Actor-Id": user_id, "X-Pin": pin}


def test_local_seed_to_scored_session_workflow(tmp_path: Path) -> None:
    client = TestClient(create_app(create_local_services(tmp_path / "trainer.sqlite3")))
    assert (
        client.post("/api/bootstrap", json={"user_id": "admin-001", "pin": "1234"}).status_code
        == 200
    )
    admin = _headers("admin-001", "1234")
    assert (
        client.post(
            "/api/users",
            headers=admin,
            json={"user_id": "instructor-001", "pin": "2345", "role": "instructor"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/users",
            headers=admin,
            json={"user_id": "trainee-001", "pin": "3456", "role": "trainee"},
        ).status_code
        == 200
    )

    assert (
        client.post(
            "/api/users",
            headers=admin,
            json={
                "user_id": "trainee-002",
                "pin": "4567",
                "role": "trainee",
                "unit_id": "other-unit",
            },
        ).json()["unit_id"]
        == "other-unit"
    )

    instructor = _headers("instructor-001", "2345")
    assert client.get("/api/units/other-unit/summary", headers=instructor).status_code == 403
    assert client.get("/api/ratings/trainee-002", headers=instructor).status_code == 403
    assert client.get("/api/ratings/not-yet-created", headers=instructor).json() == {}
    scenario_response = client.post(
        "/api/scenarios/v0",
        headers=instructor,
        json={
            "seed": 42,
            "profile": {
                "profile_id": "api-single-target",
                "difficulty": 1,
                "skill_tags": ["detection", "classification", "assessment", "response"],
            },
        },
    )
    assert scenario_response.status_code == 200
    scenario = scenario_response.json()
    assert (
        client.post(
            "/api/sessions",
            headers=instructor,
            json={"trainee_id": "trainee-002", "scenario": scenario, "selection_mode": "fixed"},
        ).status_code
        == 403
    )
    session_response = client.post(
        "/api/sessions",
        headers=instructor,
        json={"trainee_id": "trainee-001", "scenario": scenario, "selection_mode": "fixed"},
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]
    target_id = scenario["targets"][0]["target_id"]
    visible_at = scenario["targets"][0]["t_visible_ms"]
    trainee = _headers("trainee-001", "3456")

    payloads = [
        ("detect", {"target_id": target_id}),
        ("classify", {"target_id": target_id, "classification": "simulated_threat"}),
        ("assess", {"target_id": target_id, "assessment": "high"}),
        ("respond", {"target_id": target_id, "response": "report"}),
    ]
    for sequence, (event_type, payload) in enumerate(payloads):
        event = {
            "contract_version": "1.0",
            "event_id": str(uuid5(NAMESPACE_URL, f"api-{session_id}-{sequence}")),
            "session_id": session_id,
            "scenario_id": scenario["scenario_id"],
            "trainee_id": "trainee-001",
            "event_type": event_type,
            "t_offset_ms": visible_at + sequence * 100,
            "sequence": sequence,
            "payload": payload,
        }
        assert client.post("/api/events", headers=trainee, json={"event": event}).status_code == 200

    assert client.post(f"/api/sessions/{session_id}/complete", headers=trainee).status_code == 200
    scored = client.post(
        f"/api/sessions/{session_id}/score",
        headers=instructor,
        json={"doctrine_id": "generic-demo-v1", "version": "1.0.0"},
    )
    assert scored.status_code == 200
    assert scored.json()["report"]["total_score"] == 100.0
    assert scored.json()["skill_updates"]
    rescored = client.post(
        f"/api/sessions/{session_id}/score",
        headers=instructor,
        json={"doctrine_id": "generic-demo-v1", "version": "1.0.0"},
    )
    assert rescored.status_code == 200
    assert rescored.json()["skill_updates"] == []

    session = client.get(f"/api/sessions/{session_id}", headers=trainee)
    assert session.status_code == 200
    assert session.json()["rating_applied"] is True
    assert client.get(f"/api/sessions/{session_id}/replay/500", headers=trainee).status_code == 200
    assert client.get("/api/ratings/trainee-001", headers=trainee).json()["detection"] > 0
    unit_summary = client.get("/api/units/local-unit/summary", headers=instructor)
    assert unit_summary.status_code == 200
    assert unit_summary.json()["trainees"] == [
        {
            "trainee_id": "trainee-001",
            "completed_sessions": 1,
            "average_score": 100.0,
            "rating_eligible_sessions": 1,
        }
    ]


def test_adaptive_generation_and_admin_backup_routes(tmp_path: Path) -> None:
    database_path = tmp_path / "trainer.sqlite3"
    client = TestClient(create_app(create_local_services(database_path)))
    assert (
        client.post("/api/bootstrap", json={"user_id": "admin-001", "pin": "1234"}).status_code
        == 200
    )
    admin = _headers("admin-001", "1234")
    assert (
        client.post(
            "/api/users",
            headers=admin,
            json={"user_id": "instructor-001", "pin": "2345", "role": "instructor"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/users",
            headers=admin,
            json={"user_id": "trainee-001", "pin": "3456", "role": "trainee"},
        ).status_code
        == 200
    )
    instructor = _headers("instructor-001", "2345")
    selected = client.post(
        "/api/adaptive/next",
        headers=instructor,
        json={
            "trainee_id": "trainee-001",
            "options": [
                {"profile_id": "detect-drill", "difficulty": 1, "skill_tags": ["detection"]},
                {"profile_id": "classify-drill", "difficulty": 2, "skill_tags": ["classification"]},
            ],
        },
    )
    assert selected.status_code == 200
    assert selected.json()["profile_id"] == "detect-drill"
    generated = client.post(
        "/api/scenarios/v1",
        headers=instructor,
        json={
            "seed": 7,
            "profile": selected.json(),
            "swarm_size": 3,
            "clutter_count": 1,
            "terrain": "rural",
            "time_of_day": "day",
            "weather": "clear",
        },
    )
    assert generated.status_code == 200
    assert generated.json()["generator_version"] == "1.0.0"

    assert (
        client.post("/api/backups", headers=instructor, json={"name": "pilot"}).status_code == 403
    )
    backup = client.post("/api/backups", headers=admin, json={"name": "pilot"})
    assert backup.status_code == 200
    assert Path(backup.json()["path"]).is_file()

    invalid_pin = client.post(
        "/api/users",
        headers=admin,
        json={"user_id": "trainee-002", "pin": "not-a-pin", "role": "trainee"},
    )
    assert invalid_pin.status_code == 400


def test_doctrine_upload_validates_and_role_checks(tmp_path: Path) -> None:
    client = TestClient(create_app(create_local_services(tmp_path / "trainer.sqlite3")))
    client.post("/api/bootstrap", json={"user_id": "admin-001", "pin": "1234"})
    admin = _headers("admin-001", "1234")
    client.post(
        "/api/users",
        headers=admin,
        json={"user_id": "trainee-001", "pin": "3456", "role": "trainee"},
    )

    valid_yaml = (Path(__file__).resolve().parents[2] / "doctrine" / "generic_demo.yaml").read_text(
        encoding="utf-8"
    )
    forbidden = client.post(
        "/api/doctrines",
        headers=_headers("trainee-001", "3456"),
        json={"yaml_text": valid_yaml},
    )
    assert forbidden.status_code == 403

    invalid = client.post(
        "/api/doctrines",
        headers=admin,
        json={"yaml_text": "!!python/object/apply:os.system ['x']"},
    )
    assert invalid.status_code == 400
