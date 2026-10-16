# Release-readiness evidence — SIH 2026 PS 26247

**Scope:** offline, local, training-only software. This is not a weapon,
targeting, operational-doctrine, real-sensor, or real-EW product. The governing
source is [`docs/input/SIH 26247 Execution Blueprint.md`](input/SIH%2026247%20Execution%20Blueprint.md).
The repository name matches problem identifier 26247.

## Evidence policy

**Done** means the stated repository-scope behavior has an executed command or
automated test. **Partial** means code exists but a stated validation, product,
or target-environment boundary remains. The statuses do not claim every
Blueprint target is complete, and no performance number is reported unless
actually measured.

| Outcome | Status | Shipped implementation | Executed evidence | Honest boundary |
| --- | --- | --- | --- | --- |
| Desktop simulator | Partial | Godot 2D default scene, optional 3D scene, durable event outbox, local dashboard | GitHub Actions run `38745535797` imported the Godot project, loaded the 2D scene, sought seeded playback, and persisted an outbox event; actual logs are committed. | The headless CI smoke is not user interaction, target-laptop rendering, startup measurement, or FPS measurement. Local target-laptop validation remains required. |
| Scripted and procedural scenarios | Done | Scripted snapshots; deterministic V0/V1 NumPy generators; demo seeder | `make ci` ran seeded self-test and the disposable three-session demo smoke. | Synthetic training data only; no real threat data. |
| Environment and swarm variants | Partial | V1 swarm/clutter, environment fields, synthetic `t_visible_ms`, night/rain snapshot | Generator/demo asset tests passed in `make ci`. | Core data is verified; native visual presentation, realism, and performance are not. |
| Decision-tree scoring | Done | Frozen v1 scoring plus additive native v2 response-matrix/zone/critical/cap/aggregate scoring, per-node AAR | `make golden-test`: 44 passed, including 13 native-v2 production tests. | Both generic doctrines and proposed fixtures are training-only; no approved operational doctrine is supplied. |
| Individual, unit, repeated-session AAR | Partial | SQLite scores/replay, role/unit-scoped summaries, skill records | `make demo-smoke` recorded, scored, replayed, and summarized two disposable sessions. | Browser/native UI interaction and real trainee/pilot data are not manually validated. |
| Difficulty and randomisation | Done | Seeded V1 generator, adaptive selector, exact fingerprints, semantic last-five novelty guard | Generator/session tests in `make ci` reject a near duplicate, permit a distinct seed, and prove the last-five window. | Blueprint feature signature/metric/N/threshold are **not found**; Jaccard `>= 0.85`, N=5 is documented local policy, not approved calibration. |
| Offline minimal-hardware unit use | Partial | SQLite, relative API UI, source package, `launch.sh`/`launch.bat`, wheelhouse tooling | Linux wheelhouse built 28 wheels and clean `--no-index` install passed; packaged Linux launcher returned dashboard/API HTTP 200. CI run `38745535797` ran Windows setup, packaged source, `launch.bat`, and required dashboard/API HTTP 200. | No air-gapped target-laptop package run, Godot export, or hardware/FPS test is verified. Windows-hosted CI is not a user target laptop. |

**Matrix count: 3 Done / 4 Partial / 0 Missing.** A Partial row must not be
silently presented as Done.

## Native v2 contracts and G1–G10 execution

V1 schemas remain frozen and are checked against their recorded digests. V2 is
an additive family selected only by `contract_version: "2.0"`; it adds:

- class-wise outer/inner response matrices and class partial credit;
- synthetic per-target zone/inner-reach metadata;
- critical engagement and hostile-inner-zone-miss penalties;
- friendly cap and `mean_per_target` session aggregation; and
- explicit scenario/event/doctrine v1-to-v2 migration.

The proposed G1–G10 payloads at `tests/golden/golden_cases_v2.yaml` are static
native v2 inputs. `tests/golden/test_production_v2_golden.py` calls production
`score_scenario()` directly—there is no scoring sidecar. It covers G1–G9 score
outputs, G5 visibility-relative delay, G8 duplicate-ID ignore, G9 interruption
eligibility, native session persistence, and G10 invalid-doctrine retention.
They remain proposed training-only test data, not recovered Blueprint claims.

Executed proof is retained as small-text evidence:

- [`evidence/frozen-v1-contracts-2026-10-15.txt`](evidence/frozen-v1-contracts-2026-10-15.txt)
  — all three frozen v1 schema digests passed.
- [`evidence/v1-to-v2-migration-2026-10-15.txt`](evidence/v1-to-v2-migration-2026-10-15.txt)
  — scenario, event, and doctrine migration command completed.
- [`evidence/golden-test-2026-10-15.txt`](evidence/golden-test-2026-10-15.txt)
  — `44 passed in 1.47s`.

## Automated demo flow

`scripts/demo_smoke.py` automates the API-backed portions of
[`DEMO.md`](DEMO.md): it creates a temporary seeded database, validates health
and local roles, lists the generic doctrine, records abstract events, completes
and scores the scripted and night/rain sessions, reads a replay frame, and
checks unit trends/summary. Actual output is at
[`evidence/demo-smoke-2026-10-15.txt`](evidence/demo-smoke-2026-10-15.txt).
It expressly does not execute native Godot interaction/rendering/FPS.

## Wheelhouse and package evidence

The ignored `wheelhouse/` is built by `scripts/build_wheelhouse.py`; the clean
install verifier sets `PIP_NO_INDEX=1` and runs pip with `--no-index` and only
that directory. Actual Linux CPython-3.11 outputs show 28 wheels and a clean
import/check at:

- [`evidence/wheelhouse-build-2026-10-15.txt`](evidence/wheelhouse-build-2026-10-15.txt)
- [`evidence/offline-wheelhouse-2026-10-15.txt`](evidence/offline-wheelhouse-2026-10-15.txt)

No locked dependency failed to resolve in that Linux run. `PyYAML`,
`SQLAlchemy`, `numpy`, `pydantic_core`, `rpds-py`, and `ruff` are ABI/platform
wheels from that run and cannot be reused as Windows/macOS target artifacts;
see [`WHEELHOUSE.md`](WHEELHOUSE.md).

`make package` produced the source package/archive, and the packaged Linux
launcher—with a package-local link to the already pinned local virtual
environment, as the package documentation requires—served both `/api/health`
and dashboard root with HTTP 200. Actual output is at
[`evidence/package-2026-10-15.txt`](evidence/package-2026-10-15.txt) and
[`evidence/package-launch-linux-2026-10-15.txt`](evidence/package-launch-linux-2026-10-15.txt).
This does not verify Windows or an air-gapped target laptop.

## Current local verification

[`evidence/make-ci-2026-10-15.txt`](evidence/make-ci-2026-10-15.txt) records:

```text
$ make ci
All checks passed!
59 files already formatted
111 passed, 1 warning in 19.11s
{"rating_eligible": true, "scenario_id": "scenario-4f38d04fd72b2af0", "score": 100.0, "status": "ok"}
DEMO_SMOKE_OK: ...
vite ... built in 811ms
```

The one warning is Starlette's dependency deprecation warning for
`anyio.abc.BlockingPortal`; it did not fail the suite. `make ci` also ran the
API-backed demo smoke and production dashboard build.

## GitHub Actions evidence

GitHub Actions **run `38745535797`** for commit `519ccd1` completed green on
2026-10-15. Its recorded job/step result is committed at
[`evidence/github-ci-38745535797.txt`](evidence/github-ci-38745535797.txt).

1. **Godot 4 native smoke** downloaded the official `4.5.1-stable` Linux
   x86_64 binary, verified SHA-256
   `02ec53d1cc7dbb9cc6355393c61b9ab43d1244751a124f10248a4802830788cd`,
   imported the project, loaded the 2D scene, sought seeded playback, and
   checked a durable event-outbox record. The exact successful logs are
   committed at [`evidence/godot-import-ci.log`](evidence/godot-import-ci.log)
   and [`evidence/godot-headless-ci.log`](evidence/godot-headless-ci.log).
2. **Offline wheelhouse** built the lockfile wheelhouse and clean-installed it
   without an index.
3. **Windows launcher smoke** ran `scripts/setup_windows.ps1`, packaged source,
   started `launch.bat`, and required HTTP 200 from dashboard root and
   `/api/health`.

The Godot job is a CI-run headless/software-validation smoke. It reports **no
FPS number**, makes no rendering-performance claim, and is not target-laptop
validation. The workflow retains successful Godot logs as tracked evidence.

## Remaining user/target-laptop work before any real use

1. Run the actual target-laptop checklist for native Godot interactions, 2D/3D
   rendering, startup, and FPS; any FPS result must say **CI runner, software
   rendering, not target laptop** if it comes from CI, or name the actual laptop
   if locally measured.
2. Obtain/approve real doctrine and cue policy through the responsible authority;
   do not substitute the generic placeholder.
3. Build a target-specific wheelhouse and run the packaged folder without
   internet on the intended Windows/Linux/macOS laptop.
4. Conduct consented pilot/rehearsal sessions; do not claim learner transfer,
   adaptive benefit, or operational utility without recorded evidence.
