#!/usr/bin/env python3
"""Run one deterministic seed-to-score session entirely in a temporary SQLite DB."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from core.db import Role, create_session_factory, create_sqlite_engine, initialize_database
from core.generator import ScenarioProfile, generate_scenario
from core.sessions import SessionManager

ROOT = Path(__file__).resolve().parents[1]
DOCTRINE_PATH = ROOT / "doctrine" / "generic_demo.yaml"
SESSION_ID = "44444444-4444-4444-8444-444444444444"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sih26247-self-test-") as temporary_directory:
        database_path = Path(temporary_directory) / "trainer.sqlite3"
        engine = create_sqlite_engine(database_path)
        initialize_database(engine)
        manager = SessionManager(create_session_factory(engine))
        manager.create_bootstrap_admin("admin-001", "1234")
        manager.create_user(
            actor_id="admin-001",
            user_id="instructor-001",
            role=Role.INSTRUCTOR,
            pin="2345",
        )
        manager.create_user(
            actor_id="admin-001",
            user_id="trainee-001",
            role=Role.TRAINEE,
            pin="3456",
        )
        scenario = generate_scenario(
            42,
            ScenarioProfile(
                "self-test-target",
                1,
                ("detection", "classification", "assessment", "response"),
            ),
        )
        manager.create_training_session(
            actor_id="instructor-001",
            session_id=SESSION_ID,
            trainee_id="trainee-001",
            scenario=scenario,
        )
        target_id = scenario["targets"][0]["target_id"]
        visible_at = scenario["targets"][0]["t_visible_ms"]
        payloads = [
            ("detect", {"target_id": target_id}),
            ("classify", {"target_id": target_id, "classification": "simulated_threat"}),
            ("assess", {"target_id": target_id, "assessment": "high"}),
            ("respond", {"target_id": target_id, "response": "report"}),
        ]
        for sequence, (event_type, payload) in enumerate(payloads):
            manager.ingest_event(
                actor_id="trainee-001",
                event={
                    "contract_version": "1.0",
                    "event_id": str(uuid5(NAMESPACE_URL, f"self-test-{sequence}")),
                    "session_id": SESSION_ID,
                    "scenario_id": scenario["scenario_id"],
                    "trainee_id": "trainee-001",
                    "event_type": event_type,
                    "t_offset_ms": visible_at + sequence * 100,
                    "sequence": sequence,
                    "payload": payload,
                },
            )
        manager.complete_session(actor_id="trainee-001", session_id=SESSION_ID)
        report = manager.evaluate_session(
            actor_id="instructor-001",
            session_id=SESSION_ID,
            doctrine_path=DOCTRINE_PATH,
        )
        if report.total_score != 100.0:
            raise SystemExit(f"self-test expected 100.0, received {report.total_score}")
        print(
            json.dumps(
                {
                    "status": "ok",
                    "scenario_id": scenario["scenario_id"],
                    "score": report.total_score,
                    "rating_eligible": report.rating_eligible,
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
