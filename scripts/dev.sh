#!/usr/bin/env bash
# Run the local API and dashboard together. No process is exposed to an external
# service; Vite's /api proxy is only a local developer convenience.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PID=""

if [[ ! -x "${ROOT_DIR}/.venv/bin/uvicorn" || ! -d "${ROOT_DIR}/dashboard/node_modules" ]]; then
  echo "Installing locked local dependencies..."
  make -C "${ROOT_DIR}" setup
fi

cleanup() {
  if [[ -n "${API_PID}" ]] && kill -0 "${API_PID}" 2>/dev/null; then
    kill "${API_PID}" 2>/dev/null || true
    wait "${API_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

cd "${ROOT_DIR}"
"${ROOT_DIR}/.venv/bin/uvicorn" core.api.app:app --host 0.0.0.0 --port 8000 &
API_PID=$!

echo "Local API:       http://0.0.0.0:8000/api/health"
echo "Local dashboard: http://0.0.0.0:5173"
echo "Press Ctrl+C to stop both local processes."
npm --prefix dashboard run dev
