extends Control
## Stage 3 2D plan-view trainer. All actions remain abstract training events.

@onready var player: ScenarioPlayer = $ScenarioPlayer
@onready var local_api: LocalApiBridge = $LocalApiBridge
@onready var radar: Control = $Layout/Radar
@onready var timeline: HSlider = $Layout/Controls/Timeline
@onready var status_label: Label = $Layout/Controls/Status
@onready var target_select: OptionButton = $Layout/Controls/TargetSelect
@onready var classify_select: OptionButton = $Layout/Controls/ClassifySelect
@onready var assess_select: OptionButton = $Layout/Controls/AssessSelect
@onready var respond_select: OptionButton = $Layout/Controls/RespondSelect
# Resolve the autoload through the scene tree so the project compiles in a
# standalone/headless import as well as editor playback.
@onready var event_recorder: Node = get_node("/root/EventRecorder")

var markers := {}
var current_scenario: Dictionary = {}

func _ready() -> void:
    event_recorder.connect("event_recorded", local_api.sync_event)
    local_api.session_loaded.connect(_load_assigned_session)
    local_api.session_completion_finished.connect(_on_session_completion_finished)
    player.frame_changed.connect(_on_frame_changed)
    player.scenario_finished.connect(func(): status_label.text = "Replay complete")
    if local_api.session_id.is_empty():
        _load_bundled_scenario()
    else:
        local_api.load_session()

func _load_bundled_scenario() -> void:
    var file := FileAccess.open("res://scenarios/pack-v0.json", FileAccess.READ)
    if file == null:
        push_error("Bundled scenario pack is missing.")
        return
    var parsed = JSON.parse_string(file.get_as_text())
    if not (parsed is Dictionary) or parsed.get("scenarios", []).is_empty():
        push_error("Bundled scenario pack is invalid.")
        return
    _load_scenario(
        parsed.scenarios[0],
        "00000000-0000-4000-8000-000000000001",
        "trainee-001"
    )

func _load_assigned_session(snapshot: Dictionary) -> void:
    _load_scenario(snapshot.scenario, snapshot.session_id, snapshot.trainee_id)

func _load_scenario(next_scenario: Dictionary, next_session_id: String, next_trainee_id: String) -> void:
    current_scenario = next_scenario
    target_select.clear()
    for marker in markers.values():
        marker.queue_free()
    markers.clear()
    player.load_scenario(current_scenario)
    timeline.max_value = int(current_scenario.duration_ms)
    event_recorder.call(
        "configure",
        next_session_id,
        current_scenario.scenario_id,
        next_trainee_id
    )
    if next_session_id == local_api.session_id and not local_api.actor_id.is_empty():
        local_api.sync_outbox(event_recorder.call("outbox_events"))
    for target in current_scenario.targets:
        target_select.add_item(target.target_id)
        var marker := ColorRect.new()
        marker.color = Color("ff8c79") if target.affiliation == "simulated_threat" else Color("bfd65f")
        marker.size = Vector2(10, 10)
        radar.add_child(marker)
        markers[target.target_id] = marker

func _on_frame_changed(playback_ms: int, positions: Dictionary) -> void:
    timeline.value = playback_ms
    status_label.text = "%d ms" % playback_ms
    for target_id in positions:
        # ``load_scenario`` emits an initial frame before this scene has created
        # its visual markers; later playback frames update the corresponding UI.
        if not markers.has(target_id):
            continue
        var marker: ColorRect = markers[target_id]
        var position: Vector2 = positions[target_id]
        marker.position = radar.size * 0.5 + Vector2(position.x, -position.y) * 0.13 - marker.size * 0.5

func _selected_target_id() -> String:
    return target_select.get_item_text(target_select.selected)

func _on_play_pressed() -> void:
    player.set_playing(not player.playing)

func _on_timeline_value_changed(value: float) -> void:
    player.seek(int(value))

func _on_detect_pressed() -> void:
    event_recorder.call("record_detect", _selected_target_id(), player.playback_ms)

func _on_classify_pressed() -> void:
    event_recorder.call(
        "record_classify",
        _selected_target_id(),
        classify_select.get_item_text(classify_select.selected),
        player.playback_ms
    )

func _on_assess_pressed() -> void:
    event_recorder.call(
        "record_assess",
        _selected_target_id(),
        assess_select.get_item_text(assess_select.selected),
        player.playback_ms
    )

func _on_respond_pressed() -> void:
    event_recorder.call(
        "record_respond",
        _selected_target_id(),
        respond_select.get_item_text(respond_select.selected),
        player.playback_ms
    )

func _on_complete_pressed() -> void:
    player.set_playing(false)
    status_label.text = "Synchronizing local events before completion"
    local_api.complete_session()

func _on_session_completion_finished(success: bool, detail: String) -> void:
    status_label.text = "Session completed locally" if success else detail
