# Godot 4 offline client

The client is intentionally a **training playback and event-recording** app. It
contains no weapon, targeting, or real doctrine interface.

## Open the client

1. Install Godot 4 locally.
2. Open `client/project.godot`.
3. Run the default `res://2d/Main2D.tscn` scene.

The 2D scene uses the bundled deterministic pack at
`client/scenarios/pack-v0.json` when no local session is configured. It draws a
radar-style plan view and records `detect`, `classify`, `assess`, and `respond`
events as NDJSON in `user://event-outbox/`.

## Local API session flow

For a real local assignment, run the Python service, create a session, then set
these exported `LocalApiBridge` values in Godot's Inspector:

- `actor_id` — the trainee's local user ID;
- `pin` — that trainee's local PIN; and
- `session_id` — the assigned UUID from the dashboard/API.

On launch, the bridge downloads only that local session from the machine's
FastAPI service and posts event records back to it. Event records are first
written as NDJSON under `user://event-outbox/`; a later launch retries that
outbox with the same event IDs before completion. If credentials/session ID are
blank, the client remains fully offline and writes only to its local outbox.

## Views

- `2d/Main2D.tscn` — primary plan-view playback and abstract controls.
- `replay/replay_controller.gd` — logical-time replay control.
- `scenes3d/Main3D.tscn` — optional 3D presentation with day/night, haze, and
  urban/rural switches. It sets a **30 FPS cap target**; this repository makes
  no measured frame-rate claim.

The 2D scene remains the default entrypoint.
