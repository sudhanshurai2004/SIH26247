#!/usr/bin/env bash
# Build a copyable, local-only trainer folder. It contains no credentials or DB.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${ROOT_DIR}/out"
PACKAGE_DIR="${OUTPUT_DIR}/SIH26247-offline-trainer"
ARCHIVE="${OUTPUT_DIR}/SIH26247-offline-trainer.tar.gz"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to build the bundled dashboard." >&2
  exit 1
fi

cd "${ROOT_DIR}"
npm --prefix dashboard run build

rm -rf "${PACKAGE_DIR}"
mkdir -p "${PACKAGE_DIR}/api" "${PACKAGE_DIR}/dashboard" "${PACKAGE_DIR}/godot" "${PACKAGE_DIR}/data" "${PACKAGE_DIR}/docs"

# API source, frozen contracts, generic placeholder doctrine, and exact runtime
# pins are kept together so the folder has no dependency on the source checkout.
cp -R core contracts doctrine demo "${PACKAGE_DIR}/api/"
cp requirements.lock requirements-dev.lock requirements.in pyproject.toml "${PACKAGE_DIR}/api/"
mkdir -p "${PACKAGE_DIR}/api/scripts"
cp scripts/serve_local.py "${PACKAGE_DIR}/api/serve_local.py"
cp scripts/seed_demo.py scripts/build_wheelhouse.py scripts/migrate_v1_to_v2.py \
  scripts/test_offline_wheelhouse.py "${PACKAGE_DIR}/api/scripts/"
find "${PACKAGE_DIR}/api" -type d -name __pycache__ -prune -exec rm -rf {} +
find "${PACKAGE_DIR}/api" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
cp -R dashboard/dist/. "${PACKAGE_DIR}/dashboard/"
cp -R client/. "${PACKAGE_DIR}/godot/"
cp README.md LICENSE "${PACKAGE_DIR}/"
cp docs/CREDITS.md docs/DEMO.md docs/GODOT_CHECKLIST.md docs/LIMITATIONS.md docs/WHEELHOUSE.md \
  "${PACKAGE_DIR}/docs/"

cat > "${PACKAGE_DIR}/launch.sh" <<'SH'
#!/usr/bin/env bash
# One-command local launcher for Linux/macOS. It never binds a network interface.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SIH26247_DB_PATH="${SIH26247_DB_PATH:-${ROOT_DIR}/data/trainer.sqlite3}"

if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "Python 3 with the pinned local dependencies is required; see INSTALL_OFFLINE.txt." >&2
  exit 1
fi

echo "SIH 26247 offline trainer: http://127.0.0.1:8000"
exec "${PYTHON_BIN}" "${ROOT_DIR}/api/serve_local.py" --host 127.0.0.1 --port 8000
SH
chmod +x "${PACKAGE_DIR}/launch.sh"

cat > "${PACKAGE_DIR}/launch.bat" <<'BAT'
@echo off
REM One-command local launcher for Windows. It binds localhost only.
setlocal
set "ROOT_DIR=%~dp0"
if "%SIH26247_DB_PATH%"=="" set "SIH26247_DB_PATH=%ROOT_DIR%data\trainer.sqlite3"

if exist "%ROOT_DIR%.venv\Scripts\python.exe" (
  set "PYTHON_BIN=%ROOT_DIR%.venv\Scripts\python.exe"
) else (
  where py >nul 2>nul
  if errorlevel 1 (
    echo Python 3 with the pinned local dependencies is required; see INSTALL_OFFLINE.txt.
    exit /b 1
  )
  set "PYTHON_BIN=py -3"
)

echo SIH 26247 offline trainer: http://127.0.0.1:8000
%PYTHON_BIN% "%ROOT_DIR%api\serve_local.py" --host 127.0.0.1 --port 8000
BAT

cat > "${PACKAGE_DIR}/INSTALL_OFFLINE.txt" <<'TXT'
SIH 26247 Offline Trainer package
==================================

This folder contains the local API, a production-built dashboard, the Godot
project, the generic placeholder doctrine, and no user database or credentials.

Runtime requirement
-------------------
Use a Python 3.11 environment that already has the exact packages in
api/requirements.lock installed. For a fully air-gapped laptop, prepare that
virtual environment from a vetted local wheelhouse before copying this folder;
the launcher performs no download and the app makes no outbound request. The
source checkout's build_wheelhouse.py/test_offline_wheelhouse.py tooling is also
copied under api/scripts for target-specific preparation.

Start
-----
Windows: double-click launch.bat
Linux/macOS: ./launch.sh
Then open http://127.0.0.1:8000 in a browser. The API and dashboard share that
same localhost origin. Data is created only at data/trainer.sqlite3.

Optional disposable demo data
-----------------------------
Run the following before launch to seed three ready scenarios and published,
demo-only credentials in a separate database:
  python api/scripts/seed_demo.py --database data/demo-trainer.sqlite3
Then set SIH26247_DB_PATH to that database before launching. Delete the demo
database before operational use.

Godot
-----
Open godot/project.godot with Godot 4 if validating or using the optional
native client. See godot/README.md. Godot runtime/FPS claims are not implied by
this source package.
TXT

# The folder is useful for a USB handoff; the archive is useful for transport.
tar -C "${OUTPUT_DIR}" -czf "${ARCHIVE}" "SIH26247-offline-trainer"
printf 'Created offline folder: %s\nCreated archive: %s\n' "${PACKAGE_DIR}" "${ARCHIVE}"
