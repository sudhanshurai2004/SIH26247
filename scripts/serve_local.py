#!/usr/bin/env python3
"""Serve the packaged dashboard and local-only API from one localhost port.

This launcher is intentionally small so ``scripts/package_offline.sh`` can copy
it beside ``core/`` into an offline folder. It neither contacts the network nor
opens a browser automatically.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local SIH 26247 trainer package")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Local bind address (default: 127.0.0.1)"
    )
    parser.add_argument("--port", default=8000, type=int, help="Local port (default: 8000)")
    args = parser.parse_args()

    api_root = Path(__file__).resolve().parent
    package_root = api_root.parent
    dashboard_dir = package_root / "dashboard"
    if not dashboard_dir.is_dir():
        raise SystemExit(f"Built dashboard is missing: {dashboard_dir}")

    sys.path.insert(0, str(api_root))
    os.environ.setdefault("SIH26247_DB_PATH", str(package_root / "data" / "trainer.sqlite3"))

    from core.api.app import create_app

    # The launchers intentionally bind loopback only: this package is designed
    # for a single offline laptop, not a network-facing deployment.
    uvicorn.run(create_app(dashboard_dir=dashboard_dir), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
