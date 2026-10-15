extends SceneTree
## CI-only native smoke: loads the 2D scene, seeks a bundled seeded scenario,
## and proves one abstract event reaches the durable local outbox.

const MAIN_2D := preload("res://2d/Main2D.tscn")
const SMOKE_SESSION_ID := "00000000-0000-4000-8000-000000000099"

func _init() -> void:
    call_deferred("_run")

func _run() -> void:
    var scene := MAIN_2D.instantiate()
    root.add_child(scene)
    await process_frame

    var player: ScenarioPlayer = scene.get_node("ScenarioPlayer")
    if player.scenario.is_empty() or player.scenario.get("seed", -1) < 0:
        push_error("GODOT_SMOKE_FAIL: bundled seeded scenario did not load")
        quit(1)
        return
    player.seek(min(1000, int(player.scenario.duration_ms)))
    if player.playback_ms != min(1000, int(player.scenario.duration_ms)):
        push_error("GODOT_SMOKE_FAIL: seeded playback seek did not advance")
        quit(1)
        return

    var recorder := root.get_node("EventRecorder")
    recorder.call("configure", SMOKE_SESSION_ID, player.scenario.scenario_id, "trainee-001")
    var outbox_path := str(recorder.get("outbox_path"))
    if FileAccess.file_exists(outbox_path):
        DirAccess.remove_absolute(ProjectSettings.globalize_path(outbox_path))
    recorder.call("configure", SMOKE_SESSION_ID, player.scenario.scenario_id, "trainee-001")
    var target: Dictionary = player.scenario.targets[0]
    var event: Dictionary = recorder.call("record_detect", str(target.target_id), player.playback_ms)
    var outbox: Array = recorder.call("outbox_events")
    if event.is_empty() or outbox.size() != 1 or not FileAccess.file_exists(str(recorder.get("outbox_path"))):
        push_error("GODOT_SMOKE_FAIL: event outbox did not persist one abstract event")
        quit(1)
        return

    print("GODOT_SMOKE_OK: imported project, loaded 2D scene, sought seeded playback, persisted event outbox")
    quit(0)
