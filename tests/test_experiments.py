"""Pilot scripts must read persisted local data and emit real-data artifacts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from core.db import (
    Role,
    SessionStatus,
    TrainingSessionRecord,
    User,
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)

ROOT = Path(__file__).resolve().parents[1]


def test_experiment_scripts_emit_csv_and_svg_from_real_database_rows(tmp_path: Path) -> None:
    database_path = tmp_path / "trainer.sqlite3"
    engine = create_sqlite_engine(database_path)
    initialize_database(engine)
    factory = create_session_factory(engine)
    with factory.begin() as db:
        db.add(User(user_id="trainee-001", role=Role.TRAINEE.value, pin_hash="hash"))
        db.flush()
        for index, (mode, scenario_id, seed, score) in enumerate(
            [
                ("fixed", "scenario-repeat", 10, 45.0),
                ("adaptive", "scenario-repeat", 10, 70.0),
                ("adaptive", "scenario-unseen", 99, 65.0),
            ]
        ):
            db.add(
                TrainingSessionRecord(
                    session_id=f"00000000-0000-4000-8000-{index:012d}",
                    scenario_id=scenario_id,
                    trainee_id="trainee-001",
                    scenario_json=json.dumps({"seed": seed}),
                    selection_mode=mode,
                    status=SessionStatus.COMPLETED.value,
                    rating_eligible=True,
                    rating_applied=False,
                    score_json=json.dumps({"total_score": score}),
                )
            )

    output = tmp_path / "reports"
    commands = [
        [
            sys.executable,
            "experiments/adaptive_vs_fixed.py",
            "--db",
            str(database_path),
            "--out",
            str(output),
        ],
        [
            sys.executable,
            "experiments/unseen_seed_test.py",
            "--db",
            str(database_path),
            "--seen-seeds",
            "10",
            "--out",
            str(output),
        ],
        [
            sys.executable,
            "experiments/rote_learning_test.py",
            "--db",
            str(database_path),
            "--out",
            str(output),
        ],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)

    assert (output / "adaptive-vs-fixed.csv").is_file()
    assert (output / "adaptive-vs-fixed.svg").is_file()
    assert (output / "unseen-seed.csv").is_file()
    assert (output / "unseen-seed.svg").is_file()
    assert (output / "rote-learning.csv").is_file()
    assert (output / "rote-learning.svg").is_file()
