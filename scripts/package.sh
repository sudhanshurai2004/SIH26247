#!/usr/bin/env bash
# Create a reproducible source bundle for offline installation review.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${ROOT_DIR}/out"
ARCHIVE="${OUTPUT_DIR}/sih26247-offline-trainer-source.tar.gz"

mkdir -p "${OUTPUT_DIR}"
git -C "${ROOT_DIR}" archive --format=tar.gz --prefix=sih26247/ HEAD > "${ARCHIVE}"
printf 'Created %s\n' "${ARCHIVE}"
