# Decisions

This log records only decisions needed when the supplied requirements leave an
implementation choice open. Dates use the project-local Asia/Kolkata date.

## D-001 — Stage 1 contract representation (2026-10-12)

**Context:** The request refers to an attached Execution Blueprint, but no
blueprint file or attachment was available in the checked-out repository at the
start of Stage 1.

**Decision:** Implement the explicitly requested Stage 1 deliverables from the
prompt using JSON Schema Draft 2020-12 and contract version `1.0`. Scenario
times are logical millisecond offsets; event actions use `t_offset_ms`; and the
doctrine contains only abstract training choices (`monitor`, `report`,
`escalate`, `defer`). No data set, benchmark, doctrine, or performance claim
was invented.

**Consequence:** `contracts/*.schema.json` are frozen at `1.0` after Stage 1.
Before Stage 2, reconcile any conflicting blueprint field names or semantics by
adding a versioned migration rather than silently changing this contract.

## D-002 — Local development topology (2026-10-12)

**Decision:** `make dev` starts FastAPI on port 8000 and Vite on port 5173.
The dashboard is configured to use relative `/api` paths; only Vite's local
development proxy targets `127.0.0.1:8000` server-side. Browser-facing code
contains no localhost API address.

**Consequence:** The desktop product remains local-only and no runtime endpoint
is configured to send telemetry or call a remote service.

## D-003 — Demo doctrine safety boundary (2026-10-12)

**Decision:** Ship `doctrine/generic_demo.yaml` now as a clearly labelled,
abstract placeholder so later scoring has a versioned fixture. It contains no
weapon operation, targeting, electronic-warfare technique, or real doctrine.

**Consequence:** Scoring reads action weights and permitted abstract responses
exclusively from validated YAML contract data, not hard-coded values.

## D-004 — Blueprint golden-scenario limitation (2026-10-12)

**Context:** The Execution Blueprint PDF was attached for Stage 2, but its
reported `/home/user/uploads/` path was not mounted in this workspace. When
asked how to proceed, the user selected **“Proceed from the prompt only.”**

**Decision:** Implement the explicit prompt scope and add hand-checked tests
for the generic demo doctrine, without claiming those tests are Blueprint golden
scenarios. Do not invent G1–G10 inputs, scores, or benchmark data.

**Consequence:** The required Blueprint G1–G10 golden-fixture suite remains
unmeasured and must be added from the supplied source material before an MVP
lock that requires it.

## D-005 — V0 detection-delay credit curve (2026-10-12)

**Context:** Contract v1 contains doctrine-owned action weights and three
detection-delay thresholds, but no separate per-band credit coefficients.

**Decision:** Award full detection credit through `excellent_ms`, then linearly
decrease it to zero at `late_ms`; preserve `acceptable_ms` as an auditable AAR
band boundary. The formula adds no hard-coded action weight and uses only the
validated doctrine thresholds.

**Consequence:** The generic demo scoring tests state their arithmetic. Replace
this formula only through a versioned doctrine/contract decision once the
Blueprint scoring specification is available.

## D-006 — Continue from the supplied prompt when the attached PDF is unavailable (2026-10-12)

**Context:** The Execution Blueprint was attached again, but the declared
`/home/user/uploads/SIH 26247 Execution Blueprint.pdf` path is not mounted in
this coding workspace. The user explicitly asked to continue without repeated
questions.

**Decision:** Continue implementation from the explicit project prompt and the
frozen contracts. Do not claim that unavailable Blueprint-specific values (in
particular G1–G10 fixtures or performance targets) have been reproduced.

**Consequence:** Later functionality remains generic, training-only, and is
covered by real local tests. Blueprint-specific acceptance items remain labelled
unmeasured until its contents become accessible.

## D-007 — V1 sensor traces preserve the frozen scenario contract (2026-10-12)

**Context:** The frozen scenario contract records a target's precomputed
`t_visible_ms`, but has no field for a complete sensor trace.

**Decision:** Generate deterministic visibility/noise/dropout traces with
caller-local NumPy PCG64 generators. Keep the trace as a generator/replay
artifact and persist only its precomputed first-visible logical offset in the
contract scenario.

**Consequence:** V1 generation remains byte-stable for seed/profile/version and
scoring still measures detection relative to `t_visible_ms`. Adding serialized
sensor samples later requires a new contract version rather than an extra v1
field.

## D-008 — Generic adaptive model and evidence boundaries (2026-10-12)

**Decision:** Use a small persisted per-skill Elo-style adjustment with a stable
weakest-skill selector. Analyze adaptive-vs-fixed, unseen seeds, and repetition
only from recorded SQLite scored-session data; scripts refuse missing data.

**Consequence:** The project provides an auditable local pilot mechanism, not a
claim that adaptive training outperforms fixed training. No pilot result,
retention result, or student-performance number is bundled.

## D-009 — Godot validation boundary (2026-10-12)

**Decision:** Ship a Godot 4 project with a 2D default scene, local event outbox,
optional 3D presentation toggles, and a documented 30-FPS cap target. Test its
files and bundled scenario pack statically when Godot is unavailable.

**Consequence:** The source is integrated with the local API bridge, but no
runtime Godot rendering, interaction, or frame-rate result is claimed until a
Godot executable validates it on target hardware.

## D-010 — Proposed G1–G10 pack compatibility boundary (2026-10-13)

**Context:** The user supplied a hand-authored, explicitly proposed G1–G10
pack in `docs/input/` and `tests/golden/`; it is not recovered Blueprint data.
The pack's flat doctrine (`weights.time`, class-specific response matrices),
uppercase events (`DETECT`, `CLASSIFY`, `RESPOND`), and action vocabulary do
not conform to the frozen contract-v1 schema or the production generic doctrine
shape.

**Decision:** Preserve the supplied five pack files verbatim and add
`core.scoring.proposed_golden` as a test-only compatibility evaluator. It
reproduces the supplied reference scorer's timing, duplicate-ID, interruption,
critical-penalty, and friendly-cap semantics without changing the frozen
production contracts. Standard session ingestion deliberately retains stricter
behavior for a duplicate event ID bound to a *different* payload: it rejects a
conflict rather than silently ignoring it. The supplied G8 retries have
identical payloads and match exactly.

**Consequence:** G1–G10 are now automated proposed-spec regression tests, not
claims about unavailable Blueprint numbers or real doctrine. The generic
placeholder remains labelled as such. If a later Blueprint requires these
semantics in the production contract, introduce a versioned contract/doctrine
migration instead of silently widening v1.

## D-011 — Repository name matches problem identifier (2026-10-15)

**Context:** The governing execution blueprint is available as
`docs/input/SIH 26247 Execution Blueprint.md` and identifies the project as SIH
2026 PS **26247**.

**Decision:** Name the repository `SIH26247` so its name matches problem ID
26247. Replace the former identifier throughout the repository; no legacy alias
is retained.

**Consequence:** Repository, package, database, API, and documentation names
consistently use problem ID 26247.

## D-012 — Frozen-v1 Golden adapter boundary (2026-10-15)

**Decision:** Translate proposed G1–G9 targets/events into schema-valid nested
contract-v1 payloads and call production `score_scenario()` for every target.
Keep non-expressible proposed rules in a named adapter sidecar: class-specific
response matrices, outer/inner zones, critical engagement/miss penalties,
friendly-score cap, aggregate per-target mean, and the pack's source retry
count. Production now natively deduplicates identical `event_id` retries and
rejects changed-content reuse, so G8 reaches the real scorer safely. G10 stays
at the validated-doctrine repository/API boundary because it intentionally has
no scoreable event scenario.

**Consequence:** The adapter is evidence of contract translation and production
execution, not a claim that generic v1 doctrine implements the proposed or real
operational rules. See `docs/READINESS.md` for the case mapping.

## D-013 — Deterministic novelty and unit scoping (2026-10-15)

**Decision:** The session service rejects an exact V1 structural fingerprint
already assigned to the same trainee, without using wall-clock timestamps or
global randomness. A fixed scenario may still be assigned to another trainee
for a fair unit comparison. Instructors are restricted to their persisted
`unit_id` for unit summary, sessions, and ratings; admins retain local
cross-unit oversight.

**Consequence:** This is an exact-repeat guard, not the Blueprint's future
semantic “similar last N” metric. It is labelled partial rather than overstated
as a full similarity system.

## D-014 — Disposable published demo credentials (2026-10-15)

**Decision:** There is no production default account or PIN. `scripts/seed_demo.py`
creates an explicitly disposable, separate demo database only on an empty path
(or after explicit `--reset`), with documented credentials for rehearsal.
The dashboard starts with blank login fields.

**Consequence:** Demo PINs are public and must never be used for real trainees;
delete the seeded demo database before operational use.

## D-015 — Local source-package launch boundary (2026-10-15)

**Decision:** `scripts/package_offline.sh` produces a copied folder containing
the API, production-built dashboard, Godot project, frozen contracts, generic
placeholder doctrine, and Windows/Linux/macOS launchers. It does not bundle a
Python interpreter, native dependency environment, or Godot export; a vetted
preinstalled Python environment/local wheelhouse is required for an air-gapped
laptop.

**Consequence:** The launcher and app are offline at runtime, while clean-laptop
binary portability remains a user validation item rather than an unsupported
claim.

## D-016 — Additive native contract-v2 scoring boundary (2026-10-15)

**Context:** The frozen v1 contracts cannot represent a class-wise response
matrix, outer/inner response zones, critical engagement/miss penalties, a
friendly cap, or a per-target session aggregate. The hand-authored proposed
G1–G10 pack exercises those concepts but is not recovered Blueprint doctrine.

**Decision:** Keep every v1 schema and v1 scoring path intact. Add separately
named v2 scenario/event/doctrine schemas selected only by
`contract_version: "2.0"`, an explicit additive v1-to-v2 migration, and a
native v2 production scorer/session path. The migrated generic doctrine remains
training-only; it uses zero new penalties and a max-score cap so migration does
not invent punitive doctrine. Native v2 G1–G10 fixtures are explicitly proposed
training-only test data, not canonical Blueprint scores or real doctrine.

**Consequence:** The proposed matrix/zone/penalty/cap/mean semantics execute
without a v1 sidecar for v2 payloads, while deployed v1 payloads retain their
frozen interpretation.

## D-017 — Semantic novelty metric is a documented local policy (2026-10-15)

**Context:** The Execution Blueprint requires rejection when a scenario feature
signature is too similar to a trainee's last N scenarios. Its accessible text
does **not** define the feature signature, metric, N, or threshold: **not
found**.

**Decision:** Use an explicit deterministic local policy rather than claim a
Blueprint-prescribed metric: a last-five-session window, order-free feature
tokens for profile/environment/target composition/visibility bands/coarse
motion, and Jaccard similarity rejection at `>= 0.85`. Persisted assignment
sequence—not a wall clock—defines “last.” Exact v1 fingerprint rejection across
history remains as a stricter separate guard.

**Consequence:** Near clones are rejected and materially distinct generated
scenarios can pass. The policy is configurable/tested but requires later
calibration or replacement if an approved metric is supplied.

## D-018 — Offline wheelhouse scope and evidence (2026-10-15)

**Decision:** Provide a reproducible wheelhouse builder and a clean virtualenv
install test that sets `--no-index` and accepts only the supplied wheelhouse.
Keep generated third-party wheels out of Git; commit only the commands and
actual small-text evidence.

**Consequence:** The 2026-10-15 Linux CPython 3.11 run resolved all 28 locked
development wheels and passed offline install/import. Native Linux wheels are
not treated as Windows/macOS artifacts; target-specific wheelhouse and
air-gapped package validation remain required.

## D-019 — CI-native smoke evidence and Windows launcher boundary (2026-10-15)

**Decision:** Pin Godot `4.5.1-stable` Linux x86_64 to its official release
SHA-256 and run it headlessly in CI for import, 2D scene load, seeded seek, and
local event-outbox persistence. Preserve the successful raw import/smoke logs
in the repository. Add a separate `windows-latest` job that runs locked setup,
packages the source, invokes `launch.bat`, and requires dashboard/API HTTP 200.

**Consequence:** GitHub Actions run `38745535797` passed all those jobs. This is
CI-run headless/software validation, not a measured FPS result, target-laptop
rendering claim, real user-interaction result, or air-gapped target-device
certification.
