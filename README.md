# SIH 26247 — Offline Drone & Counter-Drone Threat Simulation Trainer

> **Training software only.** This repository simulates abstract trainee
> decisions for Smart India Hackathon 2026 PS **26247**. It has no weapon
> control, targeting, real doctrine, real sensor feed, or real
> electronic-warfare interface.

`SIH26247` remains in the repository/package/environment-variable names as an
intentional legacy technical identifier; the human-facing problem ID is 26247.
See [`docs/DECISIONS.md`](docs/DECISIONS.md#d-011--blueprint-source-and-corrected-problem-identifier-2026-10-15).

The local product consists of:

- a **Python/FastAPI core** for deterministic generation, SQLite sessions,
  validation, scoring, replay, and adaptive selection;
- a **Godot 4 project** with a 2D-first playback/event-outbox client and an
  optional 3D presentation; and
- a **React dashboard** for local login, AAR, replay, ratings, doctrine upload,
  and unit summaries.

There are no cloud API, telemetry, paid-service, model-download, or AGPL/YOLO
runtime dependencies. The shipped doctrine is a generic placeholder only.

## Status and boundaries

Read [`docs/READINESS.md`](docs/READINESS.md) for command-backed evidence and
an honest done/partial/missing matrix. Read
[`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) before making a presentation
claim. A pinned Godot 4.5.1 CI headless smoke has verified project import, 2D
load, seeded playback seek, and local outbox persistence; interaction, visual
rendering, and FPS remain **not verified** on an actual target laptop. Use
[`docs/GODOT_CHECKLIST.md`](docs/GODOT_CHECKLIST.md).

## Prerequisites

- Python **3.11**
- Node.js **22** and npm **10**
- Git
- Godot **4.x** only when validating/running the optional native client

Python and npm dependencies are pinned in committed lock files. Initial setup
may reach the configured package registries; application runtime uses only
local files and localhost.

## Fresh local setup and self-test

```bash
git clone https://github.com/sudhanshurai2004/SIH26247.git
cd SIH26247
make setup

# Deterministic headless seed → event → score check using a temporary SQLite DB.
make self-test

# Full lint, formatting, Python/API/dashboard tests, self-test, and production dashboard build.
make ci
```

Start the development API/dashboard pair:

```bash
make dev
```

Open `http://localhost:5173`, then verify the API at
`http://localhost:8000/api/health`. On an empty database, enter a chosen local
admin ID and PIN and click **First run: create local admin**. The UI begins with
blank credentials; it does not ship an application-startup default PIN.

The local API docs are at `http://localhost:8000/api/docs` while `make dev` is
running. Browser code uses relative `/api` requests; Vite proxies them locally
during development.

## Disposable five-minute demo kit

The repository includes three ready seeded scenarios: a scripted introduction,
a rural/day swarm, and a higher-difficulty synthetic night/rain scenario.
Create them only in a disposable demo database:

```bash
make demo-seed
SIH26247_DB_PATH="$PWD/data/demo-trainer.sqlite3" make dev
```

| User | PIN | Purpose |
| --- | ---: | --- |
| `demo-instructor` | `262471` | create/review/score local sessions |
| `demo-trainee` | `262472` | play the ready sessions |

`demo-admin` / `262470` also exists only in that disposable database. These are
published rehearsal credentials—not defaults or production secrets. Remove the
demo SQLite database after rehearsal. Exact session UUIDs, roles, AAR flow, and
the higher-difficulty second session are in [`docs/DEMO.md`](docs/DEMO.md).

For an automated API-backed rehearsal of that flow, run `make demo-smoke`.
It saves no database, uses a temporary disposable seed, and explicitly does not
claim native Godot interaction/rendering/FPS.

For a Godot-backed local session, open `client/project.godot`, configure
`LocalApiBridge` with the trainee ID/PIN/session UUID, then use the 2D scene.
The native runtime must be checked on the target laptop before a live claim;
otherwise use the documented dashboard/API fallback.

## Verification

```bash
# Proposed G1–G10 regression suite. Native v2 fixtures call production scoring
# directly; frozen-v1 adapter coverage remains separate for compatibility.
make golden-test

# Build a target-specific local Python wheelhouse, then prove clean --no-index install.
make wheelhouse
make offline-wheelhouse-test

# Dependency checks.
npm --prefix dashboard audit --audit-level=high
.venv/bin/python -m pip check
```

The G1–G10 pack is a **proposed hand-authored reference specification**, not
recovered real doctrine or canonical Blueprint data. The adapter preserves
frozen contracts and documents rules that v1 cannot express; see
[`docs/READINESS.md`](docs/READINESS.md#proposed-g1g10-production-bridge).

## Offline local source package

```bash
make package
```

This creates `out/SIH26247-offline-trainer/` and a matching `.tar.gz`, containing
an API copy, production-built dashboard, Godot project, contracts, generic
doctrine, `launch.sh`, and `launch.bat`. The launchers serve dashboard and API
from one `127.0.0.1` origin. They do **not** bundle a Python interpreter,
wheelhouse, Godot binary/export, or real doctrine; prepare a vetted target-local
Python environment/wheelhouse before an air-gapped deployment. Build and test
that wheelhouse with `make wheelhouse && make offline-wheelhouse-test`; see
[`docs/WHEELHOUSE.md`](docs/WHEELHOUSE.md). The folder’s `INSTALL_OFFLINE.txt`
describes the boundary.

## Safety, contracts, and local data

| Item | Location |
| --- | --- |
| Frozen v1 + additive native v2 schemas/migration | [`contracts/`](contracts/) and [`scripts/migrate_v1_to_v2.py`](scripts/migrate_v1_to_v2.py) |
| Generic placeholder doctrines | [`doctrine/generic_demo.yaml`](doctrine/generic_demo.yaml) and [`doctrine/generic_demo_v2.yaml`](doctrine/generic_demo_v2.yaml) |
| Three demo snapshots | [`demo/scenarios/`](demo/scenarios/) |
| Safety/release limitations | [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) |
| Licensing and dependency inventory | [`LICENSE`](LICENSE), [`docs/CREDITS.md`](docs/CREDITS.md) |

YAML is loaded with `safe_load`, then schema/semantic validation. User data is
stored through SQLAlchemy/SQLite; PINs are salted PBKDF2 hashes. Events are
idempotent by ID, conflicting reuse is rejected, and interrupted sessions are
excluded from ratings. Detection delay uses each target’s precomputed
`t_visible_ms`, never scenario start time. V1 assignment novelty includes a
local deterministic last-five semantic Jaccard check plus exact-fingerprint
rejection; the Blueprint's metric/N/threshold were not found, so the local
policy is documented rather than presented as canonical.

The `.gitignore` excludes SQLite data, backups, local environment files, and
credential material. Do not commit a real PIN, approved doctrine, operational
data, or generated local database.

## Repository map

```text
contracts/      Frozen v1 and additive v2 JSON contracts, samples, digests
core/           Generator, sensors, sessions, scoring, adaptive, replay, API
demo/           Seeded, synthetic training-only demo snapshots
client/         Godot 2D/replay/optional-3D source
dashboard/      React + Vite + TypeScript local AAR dashboard
doctrine/       Generic placeholder only
experiments/    Scripts that require real recorded sessions
docs/           Readiness, demo, limitations, decisions, credits
tests/          Automated contract/core/API/client-pack checks
scripts/        Setup helpers, demo seeder, self-test, package launcher builder
```
