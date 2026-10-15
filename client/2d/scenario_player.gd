class_name ScenarioPlayer
extends Node
## Plays only precomputed logical-time trajectory data. It never generates targets.

signal frame_changed(playback_ms: int, target_positions: Dictionary)
signal scenario_finished

var scenario: Dictionary = {}
var playback_ms := 0
var playing := false
var playback_rate := 1.0

func load_scenario(next_scenario: Dictionary) -> void:
    scenario = next_scenario
    playback_ms = 0
    playing = false
    _emit_frame()

func set_playing(next_playing: bool) -> void:
    playing = next_playing

func seek(next_playback_ms: int) -> void:
    if scenario.is_empty():
        return
    playback_ms = clampi(next_playback_ms, 0, int(scenario.duration_ms))
    _emit_frame()

func _process(delta: float) -> void:
    if not playing or scenario.is_empty():
        return
    seek(playback_ms + int(delta * 1000.0 * playback_rate))
    if playback_ms >= int(scenario.duration_ms):
        playing = false
        scenario_finished.emit()

func position_for_target(target: Dictionary, at_ms: int) -> Vector2:
    var trajectory: Array = target.trajectory
    for index in range(trajectory.size() - 1):
        var left: Dictionary = trajectory[index]
        var right: Dictionary = trajectory[index + 1]
        if int(left.t_ms) <= at_ms and at_ms <= int(right.t_ms):
            var span := int(right.t_ms) - int(left.t_ms)
            var fraction := 0.0 if span == 0 else float(at_ms - int(left.t_ms)) / float(span)
            return Vector2(
                lerpf(float(left.x_m), float(right.x_m), fraction),
                lerpf(float(left.y_m), float(right.y_m), fraction)
            )
    var final_point: Dictionary = trajectory.back()
    return Vector2(float(final_point.x_m), float(final_point.y_m))

func _emit_frame() -> void:
    var positions := {}
    for target in scenario.get("targets", []):
        positions[target.target_id] = position_for_target(target, playback_ms)
    frame_changed.emit(playback_ms, positions)
