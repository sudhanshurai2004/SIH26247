# Limitations and non-claims

This is an offline, **training-only** prototype for SIH 2026 PS **26247**. It
has no weapon control, targeting hardware interface, real doctrine, real
sensor feed, real electronic-warfare interface, cloud dependency, telemetry, or
claim of operational suitability.

## Blueprint and evaluation status

- The governing execution blueprint is available in this checkout as
  `docs/input/SIH 26247 Execution Blueprint.md`; it is planning/design input,
  not proof that all of its acceptance targets are met.
- The G1–G10 files are an explicitly **proposed hand-authored reference spec**,
  not recovered canonical Blueprint fixtures or real doctrine. Frozen v1 keeps
  its historical adapter boundary; separate native v2 fixtures now execute all
  G1–G9 scoring rules through production `score_scenario`, and G10 checks
  invalid-doctrine rejection/active-record retention. Neither path turns the
  proposed policy into approved operational doctrine or Blueprint canon.
- There is no collected pilot study, no target-user usability study, no
  measured training transfer, and no claim that adaptive selection improves
  real-world or in-simulator outcomes.

## Doctrine and synthetic cues

- `doctrine/generic_demo.yaml` and its additive v2 migration
  `doctrine/generic_demo_v2.yaml` are generic placeholders. They are not
  approved by DSSC or any operational authority and must be replaced only
  through the validated upload/review process.
- Classes, trajectories, visibility, noise, dropouts, night/rain effects, and
  response choices are abstract training data. They are not calibrated radar,
  optical, acoustic, or electronic-warfare models.
- Frozen contract v1 cannot natively express the proposed pack's protected
  zones, class-specific response matrix, critical penalties, friendly cap, or
  aggregate policy. Those generic training-only concepts are explicit in
  contract v2; a future approved requirement still needs approved doctrine and
  versioned data rather than hidden production rules.

## Novelty policy boundary

- The Blueprint calls for a feature signature comparison against the last N
  sessions, but its metric, signature, N, and threshold are **not found** in the
  accessible source. The shipped last-five/Jaccard-`0.85` policy is an explicit
  local deterministic choice, not a Blueprint-prescribed calibration.
- It prevents close synthetic repeats in the persisted last-five window and
  retains exact-fingerprint rejection across history. It has no pilot-derived
  threshold, learner study, or real-world training-effect claim.

## Godot and performance

- Godot 4 was **not installed locally** in this validation environment. GitHub
  Actions did run the pinned official Godot 4.5.1 binary headlessly: project
  import, 2D scene load, seeded seek, and local event-outbox persistence passed;
  actual logs are in `docs/evidence/godot-*-ci.log`. That CI smoke does not
  verify user interaction, visual rendering, 3D scene behavior, startup time,
  or FPS.
- The optional 3D presentation is not a release claim. The 2D scene is the
  intended fallback. Follow `docs/GODOT_CHECKLIST.md` on the actual target
  laptop and preserve recordings before making any runtime or FPS statement.
- The Blueprint's 30 FPS, under-30-second startup, 50-target generation, and
  clean-laptop performance targets have not been measured here.

## Deployment and data boundaries

- The packaging script produces a local source folder and launchers, not a
  signed installer, bundled Python runtime, vendored wheelhouse, or Godot
  export. A Linux CPython-3.11 wheelhouse clean-install command was executed,
  but an air-gapped target laptop still needs a reviewed target-specific Python
  environment/dependency wheelhouse. CI did run setup plus `launch.bat` with
  dashboard/API HTTP 200 on `windows-latest`; actual target package execution
  remains a user validation action. See `docs/WHEELHOUSE.md`.
- SQLite data and backups are local. OS disk encryption, endpoint management,
  identity policy, retention, and approval for any real deployment are outside
  this repository.
- Public demo credentials are intentionally disposable and must not be used for
  any real person or retained database. No production account is seeded by
  application startup.

See `docs/READINESS.md` for executed evidence and `docs/DECISIONS.md` for the
reasons behind these boundaries.
