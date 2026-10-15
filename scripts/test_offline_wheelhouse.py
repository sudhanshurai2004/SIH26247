#!/usr/bin/env python3
"""Prove a clean virtual environment can install from a local wheelhouse only."""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _venv_python(environment: Path) -> Path:
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline-install test for the locked wheelhouse")
    parser.add_argument(
        "--wheelhouse", type=Path, required=True, help="directory containing .whl files"
    )
    parser.add_argument(
        "--requirements",
        type=Path,
        default=ROOT / "requirements-dev.lock",
        help="pinned requirements file (default: requirements-dev.lock)",
    )
    args = parser.parse_args()
    wheelhouse = args.wheelhouse.expanduser().resolve()
    requirements = args.requirements.expanduser().resolve()
    if not wheelhouse.is_dir() or not list(wheelhouse.glob("*.whl")):
        raise SystemExit(f"wheelhouse has no wheels: {wheelhouse}")
    if not requirements.is_file():
        raise SystemExit(f"requirements file does not exist: {requirements}")

    with tempfile.TemporaryDirectory(prefix="sih26247-offline-wheelhouse-") as temp_dir:
        environment = Path(temp_dir) / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(environment)
        python = _venv_python(environment)
        offline_environment = {
            **os.environ,
            "PIP_NO_INDEX": "1",
            "PIP_FIND_LINKS": str(wheelhouse),
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }
        install = [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(wheelhouse),
            "--requirement",
            str(requirements),
        ]
        print("+", " ".join(install))
        subprocess.run(install, check=True, env=offline_environment)
        subprocess.run([str(python), "-m", "pip", "check"], check=True, env=offline_environment)
        smoke = [
            str(python),
            "-c",
            (
                "import fastapi, jsonschema, numpy, sqlalchemy, yaml; "
                "print('OFFLINE_WHEELHOUSE_IMPORT_OK')"
            ),
        ]
        subprocess.run(smoke, check=True, env=offline_environment)

    print("OFFLINE_WHEELHOUSE_TEST_OK: clean venv installed with --no-index from wheelhouse only")


if __name__ == "__main__":
    main()
