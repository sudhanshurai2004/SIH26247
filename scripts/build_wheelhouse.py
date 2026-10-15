#!/usr/bin/env python3
"""Build a local wheelhouse from the committed Python lock without installing it.

The output is intentionally ignored by Git because it contains third-party
artifacts. Use it only after reviewing/provenancing packages for the intended
operating-system and Python ABI.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a locked local Python wheelhouse")
    parser.add_argument(
        "--wheelhouse",
        type=Path,
        default=ROOT / "wheelhouse",
        help="directory for downloaded/built wheels (default: wheelhouse)",
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
    if not requirements.is_file():
        raise SystemExit(f"requirements file does not exist: {requirements}")
    wheelhouse.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "pip",
        "wheel",
        "--wheel-dir",
        str(wheelhouse),
        "--requirement",
        str(requirements),
    ]
    print("+", " ".join(command))
    subprocess.run(command, check=True)
    wheels = sorted(wheelhouse.glob("*.whl"))
    if not wheels:
        raise SystemExit("wheel build completed without producing any wheel files")
    print(f"WHEELHOUSE_BUILD_OK: {len(wheels)} wheel(s) in {wheelhouse}")


if __name__ == "__main__":
    main()
