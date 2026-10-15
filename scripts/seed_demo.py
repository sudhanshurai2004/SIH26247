#!/usr/bin/env python3
"""Seed an explicitly disposable, deterministic training-only demo database.

The script never changes a non-empty database unless the operator chooses an
empty path or explicitly passes ``--reset``. Demo PINs are published only so a
reviewer can reproduce the five-minute flow; they are not production defaults.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

DEMO_UNIT_ID = "demo-unit"
DEMO_USERS = (
    ("demo-admin", "admin", "262470"),
    ("demo-instructor", "instructor", "262471"),
    ("demo-trainee", "trainee", "262472"),
)
DEMO_SCENARIO_FILES = (
    "01-scripted-clear-single.json",
    "02-swarm-rural-day.json",
    "03-night-degraded-urban.json",
)


def main() -> None:
    # The source copy lives under scripts/ while the packaged copy lives under
    # api/scripts/. In both layouts this resolves the import root.
    sys.path.insert(0, str(REPOSITORY_ROOT))
    from core.api.runtime import create_local_services  # noqa: PLC0415
    from core.db import Role, User  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Seed a disposable local SIH 26247 demo database")
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/demo-trainer.sqlite3"),
        help="SQLite path to create (default: data/demo-trainer.sqlite3)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete the requested database before seeding it",
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable seed details")
    args = parser.parse_args()

    database_path = args.database.expanduser().resolve()
    if args.reset and database_path.exists():
        database_path.unlink()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    services = create_local_services(database_path)
    with services.session_factory() as db:
        if db.scalar(select(User.user_id).limit(1)) is not None:
            raise SystemExit(
                f"Refusing to seed non-empty database: {database_path}. Use a new path or --reset."
            )

    admin_id, _, admin_pin = DEMO_USERS[0]
    services.sessions.create_bootstrap_admin(admin_id, admin_pin, unit_id=DEMO_UNIT_ID)
    for user_id, role_name, pin in DEMO_USERS[1:]:
        services.sessions.create_user(
            actor_id=admin_id,
            user_id=user_id,
            role=Role(role_name),
            pin=pin,
            unit_id=DEMO_UNIT_ID,
        )

    doctrine_path = Path(__file__).resolve().parents[1] / "doctrine" / "generic_demo.yaml"
    services.doctrines.upload(
        actor_id=admin_id, yaml_text=doctrine_path.read_text(encoding="utf-8")
    )

    scenarios_dir = Path(__file__).resolve().parents[1] / "demo" / "scenarios"
    session_ids: dict[str, str] = {}
    for index, filename in enumerate(DEMO_SCENARIO_FILES, start=1):
        scenario = json.loads((scenarios_dir / filename).read_text(encoding="utf-8"))
        # UUIDs are stable so the Godot local bridge can be configured without
        # reading a generated random ID during a live demo.
        session_id = f"2624700{index}-0000-4000-8000-00000000000{index}"
        services.sessions.create_training_session(
            actor_id="demo-instructor",
            session_id=session_id,
            trainee_id="demo-trainee",
            scenario=scenario,
            selection_mode="fixed",
        )
        session_ids[filename] = session_id

    payload = {
        "database": str(database_path),
        "unit_id": DEMO_UNIT_ID,
        "users": [
            {"user_id": user_id, "role": role_name, "pin": pin}
            for user_id, role_name, pin in DEMO_USERS
        ],
        "sessions": session_ids,
        "doctrine": {"doctrine_id": "generic-demo-v1", "version": "1.0.0"},
        "warning": "Demo-only credentials. Delete this disposable database before operational use.",
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Seeded training-only demo database: {database_path}")
        print("Demo instructor: demo-instructor / PIN 262471")
        print("Demo trainee: demo-trainee / PIN 262472")
        for filename, session_id in session_ids.items():
            print(f"{filename}: {session_id}")
        print("Delete this demo database before operational use.")


if __name__ == "__main__":
    main()
