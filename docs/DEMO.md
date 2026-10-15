# Five-minute offline demo flow — SIH 2026 PS 26247

> **Safety boundary:** this is synthetic, training-only software. Demonstrate
> abstract detect/classify/assess/report decisions only—never claim weapon,
> targeting, real doctrine, or EW capability.

## One-time rehearsal setup

```bash
make setup
make demo-seed                         # creates ignored data/demo-trainer.sqlite3
SIH26247_DB_PATH="$PWD/data/demo-trainer.sqlite3" make dev
```

Open `http://localhost:5173`. The demo seed command is intentionally explicit:
it refuses a non-empty database unless `--reset` is provided. It does **not**
seed a production/default account.

| Demo identity | PIN | Role | Unit |
| --- | ---: | --- | --- |
| `demo-admin` | `262470` | admin | `demo-unit` |
| `demo-instructor` | `262471` | instructor | `demo-unit` |
| `demo-trainee` | `262472` | trainee | `demo-unit` |

These are public rehearsal credentials only. Delete the demo SQLite file before
any non-demo use.

## Automated rehearsal evidence

Run the API-backed, disposable version of the complete scripted flow with:

```bash
make demo-smoke
```

It seeds the three ready sessions, checks health and both local roles, lists the
generic doctrine, records/ingests abstract event sequences for the scripted and
night/rain sessions, completes and scores them, reads a replay frame, and checks
unit trends/summary. Its actual 2026-10-15 output is saved at
[`evidence/demo-smoke-2026-10-15.txt`](evidence/demo-smoke-2026-10-15.txt).
It deliberately does **not** run native Godot interaction, rendering, or FPS;
the live-client step below remains conditional on target-laptop validation.

## Ready sessions

| Session | Snapshot | Seed | Difficulty | UUID |
| --- | --- | ---: | ---: | --- |
| Scripted introduction | one abstract target, clear/day | 2624701 | 1 | `26247001-0000-4000-8000-000000000001` |
| Swarm | six simulated swarm members + two abstract distractors, rural/day | 2624702 | 2 | `26247002-0000-4000-8000-000000000002` |
| Higher-difficulty second session | three simulated members + clutter, urban/night/rain synthetic sensor conditions | 2624703 | 3 | `26247003-0000-4000-8000-000000000003` |

The snapshots live in `demo/scenarios/`; see their README for the synthetic
sensor disclaimer. All three are seeded and repeatable.

## Timed flow

| Time | Operator action | What it shows |
| --- | --- | --- |
| 0:00–0:30 | With Wi-Fi disabled if the target laptop policy permits, start the local service; show `/api/health` and the dashboard’s training-only wording. | Local service, no cloud path. |
| 0:30–0:55 | Sign in as `demo-instructor`; open **Validated doctrines** and point out the generic-placeholder label. | Doctrine is validated data, not a real procedure. |
| 0:55–1:20 | Select the scripted introduction from Sessions. | A seeded, preloaded scripted scenario. |
| 1:20–2:10 | If Godot has been validated on the actual laptop, configure `LocalApiBridge` with `demo-trainee` / `262472` and the first UUID; make abstract detect, classify, assess, and report choices, then complete. | Local event outbox/retry and trainee decision capture. |
| 2:10–2:45 | Back as the instructor, refresh, select the completed session, and choose **Score session**. | Per-node AAR, detection delay from `t_visible`, and rating eligibility. |
| 2:45–3:20 | Move the replay slider and inspect event timeline/AAR. | Deterministic replay and explainable score. |
| 3:20–3:45 | Show **Unit trends** and **Per-trainee AAR** for `demo-unit`. State that it is demo data, not measured readiness. | Individual/unit/repeated-session view. |
| 3:45–4:35 | Run the ready difficulty-3 night/rain session using the third UUID, then score it. | Higher-difficulty, environment/degradation, and swarm/clutter variant. |
| 4:35–5:00 | Show `docs/LIMITATIONS.md` / `docs/GODOT_CHECKLIST.md`; state that the 3D runtime/FPS and real-world transfer are not verified. | Honest scope and safety boundary. |

## If native Godot has not been validated

Do **not** claim the native client works. Use the API/dashboard AAR already
created by the headless self-test or explain the event-to-score flow from the
session timeline, then show the checklist. The five-minute flow remains a
rehearsal script; it is not evidence of unrun Godot interaction.

## Higher-difficulty fresh follow-up

For a distinct adaptive practice session after the ready pack, sign in as the
instructor, change the dashboard seed to `2624704`, choose **Create adaptive
demo**, complete it as the trainee, then score it. If a same-trainee V1
fingerprint is reused, the service rejects it; choose a new deliberate seed.
This demonstrates the deterministic semantic last-five novelty guard plus the
stricter exact-fingerprint guard. The local Jaccard feature metric and its
`0.85` threshold are documented policy, not claimed Blueprint-prescribed values
(the Blueprint metric/N/threshold were not found).

## Reset after rehearsal

Stop `make dev` and remove the disposable database:

```bash
rm -f data/demo-trainer.sqlite3 data/demo-trainer.sqlite3-*
```

On Windows, delete `data\demo-trainer.sqlite3` and its SQLite sidecars. Retain
only approved, non-demo local data under the organisation’s policy.
