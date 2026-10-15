class_name ReplayController
extends Node
## Keeps replay on logical time. Rendering clients receive only precomputed frames.

signal replay_seeked(playback_ms: int)

@export var player_path: NodePath
@onready var player: ScenarioPlayer = get_node(player_path)

func seek(playback_ms: int) -> void:
    player.seek(playback_ms)
    replay_seeked.emit(player.playback_ms)

func set_speed(rate: float) -> void:
    player.playback_rate = clampf(rate, 0.25, 4.0)
